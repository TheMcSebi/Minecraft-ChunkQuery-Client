# Minecraft-ChunkQuery-Client
Minecraft heightmap renderer proof-of-concept

## Description

Simple heightmap renderer for displaying part of a minecraft world.

Consists of a Flask webserver and a Python class for dealing with chunk data loaded from servers using this plugin: https://github.com/TheMcSebi/Minecraft-ChunkViewer-Plugin

## Currently included

- ChunkStorage class:
  - Load chunk data from the plugin server
  - Cache data on disk to avoid duplicate downloads
  - Render chunk data to texture- and height map
- Flask webserver
  - Display those chunks as a heightmap on the web browser
- Some scripts for processing block textures and extracting primary colors

# Setup

- Create a Minecraft Server with PaperMC.
  I tested this with 1.20.1, but in theory future versions should work, too.
- Put the plugin jar (TODO: add link) into the server's plugins directory
- Install the python dependencies from requirements.txt: `pip install -r requirements.txt`
- Start the server: `python server.py`

# Notes on future work

As this is just meant to be a simple POC, I propably won't be putting much further work into this. This project was implemented in just a few hours of work.  
If you want to play with this on your own, feel free to see this as a jump start on (what chatgpt called) a "unique and interesting" project.  
To set up the development environment I followed this tutorial: https://www.youtube.com/watch?v=tnJZMaoMPhE  
I used ChatGPT for suggesting a frontend library to use as a basic heightmap renderer. Among the top suggestions I found Babylon.js, which is why the javascript code for displaying the generated image data is taken to 99,5% from the example at https://doc.babylonjs.com/features/featuresDeepDive/mesh/creation/set/height_map  
To get the job done as quickly as possible, I implemented most of the functionality on the python side of the application. ChatGPT was also a great help while avoiding reading actual paper api documentation.  
