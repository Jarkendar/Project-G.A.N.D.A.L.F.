# Gemini transcript bookmarklet

A browser bookmarklet that extracts the full conversation from a [gemini.google.com](https://gemini.google.com) chat and copies it to the clipboard as plain text. Useful for feeding past conversations into **B.I.L.B.O.** for ingestion into `kb_conversations`.

## Output format

```
Me: <user message>

Gemini: <assistant response>

Me: <next user message>

Gemini: <next assistant response>
```

## Installation

1. Create a new bookmark in your browser.
2. Set the name to e.g. `Copy Gemini chat`.
3. Paste the code below into the URL field (must start with `javascript:`).
4. Save.

## Usage

1. Open any conversation on [gemini.google.com](https://gemini.google.com).
2. Click the bookmarklet.
3. The transcript is copied to your clipboard. An alert reports how many turns were captured.

If clipboard access is blocked, the transcript opens in a new tab as preformatted text — copy from there manually.

## Code

```javascript
javascript:(function(){
  var out=[];
  var turns=document.querySelectorAll('.conversation-container');
  turns.forEach(function(turn){
    var userLines=turn.querySelectorAll('.query-text-line');
    if(userLines.length){
      var txt=Array.from(userLines).map(function(l){return l.innerText.trim();}).join(' ');
      if(txt) out.push('Me: '+txt);
    }
    var botMsg=turn.querySelector('.markdown.markdown-main-panel');
    if(botMsg){
      var txt=botMsg.innerText.trim();
      if(txt) out.push('Gemini: '+txt);
    }
  });
  var result=out.join('\n\n');
  navigator.clipboard.writeText(result).then(function(){
    alert('Transcript copied! ('+turns.length+' turns)');
  }).catch(function(){
    var w=window.open();
    w.document.write('<pre style="white-space:pre-wrap">'+result.replace(/</g,'&lt;')+'</pre>');
  });
})();
```

## Known limitations

- **Selector drift.** Gemini's web UI may rename class names between deployments. If the alert reports `0 turns`, inspect the DOM and update the selectors (`.conversation-container`, `.query-text-line`, `.markdown.markdown-main-panel`).
- **Tool outputs and rich UI elements** (image generation, Workspace previews, code execution panels) are not specifically extracted — only their text representation inside the main markdown container is captured.
