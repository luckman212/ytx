![](yt-hat.png)

## YouTube URL Extractor

Finds any YouTube URLs in the current clipboard text, and queries Google's YouTube V3 API to fetch metadata about each one. Copy the results as Markdown with short youtu.be format links.

### How to use

Copy some text containing YouTube URLs to the clipboard, then activate this workflow's trigger keyword.

Results are displayed in a list, reverse-sorted by video post date. The complete results can be copied as Markdown links ("Copy all items in Markdown link format" option), or opened individually. Hold the <kbd>OPTION</kbd> key to toggle the subtitle between the post date and the full title if it's long/truncated. If you action the "Copy all items..." option while holding <kbd>OPTION</kbd>, the results will be shown in a TextView first to allow the list to be edited before copying.

QuickLook is enabled for the items as a simple “live preview” by pressing the <kbd>SHIFT</kbd> key with a result selected.

<img src="example.png" />

#### Example of the normalized copied output

```
- [REPLACE Spotlight with Alfred 5: The Ultimate Productivity Hack for Mac Users (23:02)](https://youtu.be/fFI_KgKLvuU) - 2025-01-10
- [ChatGPT / DALL-E workflow for Alfred 5 (1:57)](https://youtu.be/eNPMqyV8psY) - 2024-03-18
- [BEST Productivity Mac App: Alfred - Setup & Walkthrough (13:19)](https://youtu.be/NbTvpxhGwvs) - 2023-06-29
- [The Power of Alfred Workflows (6:38)](https://youtu.be/KhWOaWk1hew) - 2022-11-16
- [Efficient Tips (#2) - Alfred Workflows | Top picks and how to create them (18:27)](https://youtu.be/U9wJmgd9kAw) - 2020-01-27
```

### ⚠️ Requires an API key!

You must create a Google Cloud project at https://console.cloud.google.com, grant it access to the [YouTube V3 API](https://developers.google.com/youtube/v3/docs/), and then create an API key credential for use within this workflow.

Once you have your key, you can input it directly, or store it in 1Password if you prefer (create a new 'API Credential' item, and copy its UUID)

<img src="1pass.png" width="300" />

### Terminal CLI

The `ytx.py` script contained in this workflow has no special dependencies, and is designed to run standalone in a shell as well. Create a symlink for convenience by right-clicking the workflow in Alfred, choosing **Open in Terminal** and then typing: `ln -s ytx.py /usr/local/bin`.

Once that's done, the syntax of the command is:

```
ytx.py [-cmx] <url-or-filename> [url2...]
```

- Args can be YouTube URLs or filenames (if a filename is used, it will be scanned for URLs)
- You can mix & match URLs and filenames as args
- Default output is JSON
- The `-c` option will use the clipboard contents instead of args
- The `-m` option will output Markdown format links
- The `-x` option will output Markdown links with a little more detail (duration and date posted)
