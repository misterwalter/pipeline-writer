# pipeline-writer
*As much fiction as you could possibly ask for*

This is an experimental tool that I put together to see if I could get AI to write a novel. It technically does that, but I am compelled by honor to be clear from the start that it does not write good novels, rather it tends towards pretentious and repetitive novellas, which is still pretty cool IMO. I haven't let any of my "real" writing near this, and once you experiment with it, I suspect you will understand why.

All that said, I learned a lot of interesting and fun lessons from the process, so I wanted to share this to share those lessons!

## Requirements
Before running this script, ensure you have the following:
- Python 3.x: Standard installation.
- Ollama: Must be installed and running locally.
- RAM: This is extremely memory-intensive. The recommended model requires approximately 60GB of RAM. It will likely fail or crash on systems with less memory, or if you try to use smaller models.
- Network: An internet connection is required initially to download the model weights. Note that the initial download for the recommended model will be quite slow as it is massive. However once the pieces are in place there is no need for an ongoing internet connection.
- Requests Library: Install via pip install requests.

## How It Works
The script operates in a continuous loop, checking for story folders and advancing them through two stages:

Stage 1: Seed to Outline: Reads your _seed.md and generates a detailed chapter-by-chapter outline (_outline.md).

Stage 2: Chapter Generation: Iteratively writes chapters. It generates multiple drafts (iterations) for each chapter until a "canonical" version is manually written or promoted by the user.

## File Structure
To start a new story:

Create a new folder inside pipeline_stories with the name of your story (e.g., My_Novel).
Inside that folder, create a _seed.md file containing your story concept.

Tip: Include TARGET_LENGTH: [int] at the top of the seed file to specify the number of chapters. The AI will not always hold to this, but you can influence its decision a bit this way.
Quality: The more detail you provide in _seed.md, the better the resulting _outline.md will be.

(Optional) Create _prompt.md for specific guidance for the AI, or _sample.md to provide a prose sample for the AI to emulate. Be sure to keep these short though as they will take up precious context that is needed for the outline and previous chapters.

## The Workflow
The script runs automatically once started. It will:
- Generate an outline if one is missing.
- Generate iteration a for Chapter 1.
- Wait for you to review and edit.
- Once you rename the iteration file to the canonical name (see below), it will generate iteration a for Chapter 2, using the canonical Chapter 1 as context.

Crucial Step: Promoting Chapters
The script does not automatically decide which draft is "good enough." It generates iterations named StoryName_01a.md, StoryName_01b.md, etc. You must either manually edit the best iteration and rename it to remove the letter suffix (e.g., rename StoryName_01a.md to StoryName_01.md), or write your own canonical chapter as inspired (or goaded) by the other draft chapters.
Progression: The script detects the canonical file (e.g., StoryName_01.md) and will only proceed to generate Chapter 2 once the canonical Chapter 1 exists, unless the _config.md file instructs it to push forward using draft "a" as canon.

## Configuration
Each story folder can have its own _config.md file. If missing, the script creates a default one.
Key Settings:
```
model: The Ollama model tag to use.
iteration_count: How many drafts to generate before stopping (default: 4).
push_forward: If true, the script attempts to move to the next chapter immediately after a canonical file is detected. If false, it waits for manual intervention.
context_truncation_limit: Maximum characters to keep from previous chapters to fit within context limits (default: 2000).
```

## Tips for Best Results
Context Limits: The script truncates previous chapters to fit the context window. Writing concise, high-density prose in your canonical chapters helps the AI maintain continuity.
You Can Write Too: Treat the outputs as a rough draft. The AI can write, but you can probably make its writing better. So get in there!
Hardware: If you experience crashes, your system likely ran out of RAM. This script is not optimized for low-memory environments.
Don't Be Afraid To Pause: It can be distracting and wasteful to have your server cranking out chapters from an outline that you are actively editing. If you detect a problem with how the AI is working on a story, don't hesitate to pause it so it isn't burning cycles for no reason as you deliberate.
Abliterated Model: In my experience, most storytelling models will skip over conflict and bad times in a story if they are not abliterated, and you may even end up getting "chapters" that are just the bot refusing to continue the story more often than you might think. Abliterated models are largely necessary for that reason, though you of course remain free to try whatever model you like with it. 

## Obsidian For Convenience
The script was meant to run within a synced obsidian notes folder, so all user files are `.md` files. Given the long generation times and high RAM usage, I do not recommend running this on a computer that you intend to keep using actively while it's running. Therefore everything is optimized for using Obsidian Sync from another device to instruct the AI and do the needful in terms of editing, writing, and of course, reading.


## The Real And Hidden Benefit
Because the content that's generated tends to be in the right general shape, but quite bad, this script has actually gotten me back into writing fiction by virtue of the habits I've built via editing and replacing chapters in the stories that it generates. I've actually started working on a real novel and some short stories just because this script got my literary momentum up! Additionally, the slow pace of generation on my machine has, at times, left me particularly eager to write the rest of the story myself. As it turns out, the fact that it seems only more advanced models are able to match the format and context requirements to generate correctly, has become another incentive to get deeper into the loop as a human user.

All in all, I'm a little disappointed that this can't just generate even decent quality freely, but it makes sense given the current state of technology and my budget of "a little linux box in my apartment with 64GB of RAM and an integrated GPU". I think that it might be more disruptive to my processes if it was running faster than it is, but as it is, it's a fascinating project that somehow got me writing again, so I wont complain too much.


## License
This code is released under a Creative Commons Attribution-NonCommercial 4.0 International license.
https://creativecommons.org/licenses/by-nc/4.0/
In short, that basically means that you can copy it, learn from it, play with it, and more. However, you cannot sell it or use it for commercial purposes, and you should credit me with its creation when sharing it or things that use it.
It's also worth noting that the stories that it generates are likely to be uncopyrightable, but I'm a text file, not a lawyer, so you can look into that on your own.


## Future Action
I have no specific plans to update this, but I probably will a little bit. I tweak it from time to time. If you have contributions to offer then I'd be very curious to see them!
