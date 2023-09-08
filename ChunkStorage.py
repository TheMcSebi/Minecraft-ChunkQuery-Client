from PIL import Image, ImageDraw, ImageEnhance
from block_colors import BLOCK_COLORS
from io import BytesIO
import requests, queue, threading, time, pickle
import numpy as np

MAX_WORLD_HEIGHT = 320
CHUNK_SIZE = 16
DEFAULT_WORLD_NAME = "world"
CACHE_FILE_NAME = "cache_file.pickle"
NUM_DOWNLOAD_WORKERS = 6

class ChunkStorage:
    def __init__(self, data: dict = None, auto_save: bool = True, api_server: str = "127.0.0.1:8090") -> None:
        if data is None:
            self._data = {}
        else:
            self._data = data

        self.download_queue = queue.Queue()
        self.render_queue = queue.Queue()
        self._images = {}
        self.auto_save = auto_save
        self.api_server = api_server

        try:
            with open(CACHE_FILE_NAME, 'rb') as f:
                self._data = pickle.load(f)
        except:
            print("No cache found")

        for i in range(NUM_DOWNLOAD_WORKERS):
            threading.Thread(target=self._download_worker, args=(i, ), name=f"DownloadWorker[{i}]", daemon=True).start()

        threading.Thread(target=self._render_worker, name="RenderWorker", daemon=True).start()


    def _download_worker(self, worker_num: int) -> None:
        """
        Worker thread for downloading chunks from the server
        """
        while True:
            cx, cz, world = self.download_queue.get()

            print(f"[{worker_num}] Downloading chunk {cx}, {cz} in {world}", flush=True)

            chunk_data = self._download_chunk(cx, cz, world=world)

            if chunk_data is None:
                continue

            if "error" in chunk_data:
                print(f"[{worker_num}] Error loading chunk {cx}, {cz}: {chunk_data['error']}", flush=True)
                continue

            self._set_chunk(cx, cz, chunk_data, world=world)

            print(f"[{worker_num}] Downloaded chunk {cx}, {cz}; queue size: {self.download_queue.qsize()}", flush=True)

            self.download_queue.task_done()

    def _download_chunk(self, cx: int, cz: int, world: str = DEFAULT_WORLD_NAME) -> dict | None:
        """
        Downloads a given chunk from the server
        """
        try:
            resp = requests.post(f'http://{self.api_server}/get_chunk_data', json={"cx": cx, "cz": cz, "world": world})
        except Exception as e:
            print(f"Error loading chunk {cx}, {cz} in {world}: Could not connect to server: {e}")
            return None

        try:
            return resp.json()
        except Exception as e:
            print(f"Error loading chunk {cx}, {cz} in {world}: Could not parse response: {e}")
            return None

    def _set_chunk(self, cx: int, cz: int, chunk_data: dict, world: str = DEFAULT_WORLD_NAME) -> None:
        """
        Writes a given chunk to the cache and occasionally writes data to disk
        """
        self._data[f"{world},{cx},{cz}"] = chunk_data


    def _load_chunk(self, cx: int, cz: int, world: str = DEFAULT_WORLD_NAME):
        """
        Appends a chunk to the download queue to asynchronously retrieve it from the server
        """
        self.download_queue.put((cx, cz, world))

    def _get_chunk(self, cx: int, cz: int, world: str = DEFAULT_WORLD_NAME) -> dict | None:
        """
        Retrieve a chunk from the cache
        """
        return self._data.get(f"{world},{cx},{cz}", None)

    def _chunk_available(self, cx: int, cz: int, world: str = DEFAULT_WORLD_NAME) -> bool:
        """
        Returns whether a chunk is available in the cache
        """
        return f"{world},{cx},{cz}" in self._data

    def save(self) -> None:
        """
        Saves the cache to disk
        """
        with open(CACHE_FILE_NAME, 'wb') as f:
            pickle.dump(self._data, f)
        print("Info: Saved cache to disk")

    def load(self, center_chunk: tuple[int, int] = (0, 0), radius: int = 16, world: str = DEFAULT_WORLD_NAME, force_update: bool = False) -> None:
        """
        Loads chunks around a given center chunk
        """
        for cx in range(-radius, radius):
            for cz in range(-radius, radius):
                if force_update or not self._chunk_available(cx+center_chunk[0], cz+center_chunk[1], world=world):
                    self._load_chunk(cx+center_chunk[0], cz+center_chunk[1], world=world)

    def render(self, center_chunk: tuple[int, int] = (0, 0), radius: int = 16, world: str = DEFAULT_WORLD_NAME, player: str = "default") -> None:
        """
        Adds a request to the render queue
        """
        self.render_queue.put((center_chunk, radius, world, player))

    def _render_worker(self) -> None:
        """
        Generates heightmap and texture map images from the loaded chunks
        Also calls the save function to store downloaded chunks
        """
        while True:
            center_chunk, radius, world, player = self.render_queue.get()
            t0 = time.time()
            self.download_queue.join() # after receiving a request, wait until the downloads have finished
            t1 = time.time()
            print(f"Downloaded chunks in {t1-t0:.2f} seconds")

            size_x = radius * 2 * CHUNK_SIZE
            size_y = radius * 2 * CHUNK_SIZE

            textures_image = Image.new("RGB", (size_x, size_y), (0, 0, 0))
            textures_draw = ImageDraw.Draw(textures_image)
            heightmap_array = np.zeros((size_x, size_y)) # conversion to PIL image happens afterwards

            min_y = float('inf')
            max_y = float('-inf')
            block_counts = {}
            unassigned_blocks = set()

            for cx in range(-radius, radius):
                for cz in range(-radius, radius):
                    c = self._get_chunk(cx+center_chunk[0], cz+center_chunk[1], world=world)
                    if c is None:
                        continue

                    base_x = (cx + radius) * CHUNK_SIZE
                    base_z = (cz + radius) * CHUNK_SIZE

                    for x in range(0, CHUNK_SIZE):
                        for z in range(0, CHUNK_SIZE):
                            y = c["height"][x][z]
                            min_y = min(min_y, y)
                            max_y = max(max_y, y)

                            pixel_x = base_x + x
                            pixel_z = base_z + z

                            heightmap_array[pixel_x, pixel_z] = y # store height for later use
                            block = c["blocks"][x][z]

                            # count block occurences
                            if block not in block_counts:
                                block_counts[block] = 0
                            block_counts[block] += 1

                            # draw on texture map
                            col = BLOCK_COLORS.get(block, None)
                            if col == None:
                                unassigned_blocks.add(block)
                                col = (255, 0, 0)
                            textures_draw.point((pixel_x, pixel_z), fill=col)

            # convert numpy 2d array to heightmap PIL image
            heightmap_normalized = ((heightmap_array - min_y) / (max_y - min_y)) * 255
            heightmap_normalized = np.flipud(np.rot90(heightmap_normalized)).astype(np.uint8)
            heightmap_image = Image.fromarray(heightmap_normalized, 'L')

            # convert to bytes in memory
            textures = BytesIO()
            heightmap = BytesIO()
            textures_image.save(textures, format="PNG")
            heightmap_image.save(heightmap, format="PNG")

            print(f"Generated images in {time.time()-t1:.2f} seconds")
            print("not assigned blocks:", unassigned_blocks)
            print("block counts:", block_counts)


            self._images[f"{player}-textures"] = textures.getvalue()
            self._images[f"{player}-height"] = heightmap.getvalue()

            if self.auto_save:
                self.save()

    def get_image(self, player: str, imtype: str) -> BytesIO:
        """
        Retrieves a rendered image from the cache
        """
        if imtype not in ("textures", "height"):
            raise ValueError("Invalid image type")

        try:
            return BytesIO(self._images[f"{player}-{imtype}"])
        except:
            raise ValueError(f"Image for player {player} not available")


    def get_rectangular_array(self) -> tuple[list[list[dict]], tuple[int, int], tuple[int, int]]:
        """
        Convert entire chunk database to a rectangular array for further processing
        """
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')

        # Determine the boundaries
        for key in self._data.keys():
            x, y = map(int, key.split(","))
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)

        # Create and populate the 2D list
        rows = max_x - min_x + 1
        cols = max_y - min_y + 1
        rectangular_array = [[None for _ in range(cols)] for _ in range(rows)]

        for key, value in self._data.items():
            x, y = map(int, key.split(","))
            internal_x = x - min_x
            internal_y = y - min_y
            rectangular_array[internal_x][internal_y] = value

        return rectangular_array, (min_x, min_y), (rows, cols)

    # def _update_world_format(self, world: str = DEFAULT_WORLD_NAME) -> None:
    #     # run once
    #     data_new = {}
    #     for key in self._data.keys():
    #         cx, cz = map(int, key.split(","))
    #         data_new[f"{world},{cx},{cz}"] = self._data[key]
    #     self._data = data_new
    #     self.save()