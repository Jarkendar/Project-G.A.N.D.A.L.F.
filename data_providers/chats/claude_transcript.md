# Claude transcript bookmarklet

A browser bookmarklet that extracts the full conversation from a [claude.ai](https://claude.ai) chat and copies it to the clipboard as plain text. Useful for feeding past conversations into **B.I.L.B.O.** for ingestion into `kb_conversations`.

## Output format

```
Me: <user message>

Claude: <assistant response>

Me: <next user message>

Claude: <next assistant response>
```

Messages are interleaved in DOM order, so the chronological flow is preserved.

## Installation

1. Create a new bookmark in your browser.
2. Set the name to e.g. `Copy Claude chat`.
3. Paste the code below into the URL field (must start with `javascript:`).
4. Save.

## Usage

1. Open any conversation on [claude.ai](https://claude.ai).
2. For long conversations: scroll to the top first to force-render every message (claude.ai virtualises the message list — off-screen turns may not be in the DOM until you scroll past them).
3. Click the bookmarklet.
4. The transcript is copied to your clipboard. An alert reports how many messages were captured.

If clipboard access is blocked (e.g. browser policy), the transcript opens in a new tab as preformatted text — copy from there manually.

## Code

```javascript
javascript:(function(){
  var out=[];
  var userMsgs=document.querySelectorAll('[data-testid="user-message"], div.font-user-message');
  var botMsgs=document.querySelectorAll('div.font-claude-message, div.font-claude-response');
  var all=[];
  userMsgs.forEach(function(el){all.push({el:el,role:'Me'});});
  botMsgs.forEach(function(el){all.push({el:el,role:'Claude'});});
  all.sort(function(a,b){
    var pos=a.el.compareDocumentPosition(b.el);
    if(pos & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
    if(pos & Node.DOCUMENT_POSITION_PRECEDING) return 1;
    return 0;
  });
  all.forEach(function(item){
    var txt=item.el.innerText.trim();
    if(txt) out.push(item.role+': '+txt);
  });
  var result=out.join('\n\n');
  navigator.clipboard.writeText(result).then(function(){
    alert('Transcript copied! ('+all.length+' messages)');
  }).catch(function(){
    var w=window.open();
    w.document.write('<pre style="white-space:pre-wrap">'+result.replace(/</g,'&lt;')+'</pre>');
  });
})();
```

## Known limitations

- **Artifacts are not captured.** Artifact panels render outside the message container, so any code, document, or canvas produced by Claude as an artifact will not be in the transcript. Only the assistant's surrounding prose is captured.
- **Extended thinking blocks** are captured only if you manually expand them before running the bookmarklet. Collapsed thinking content is hidden from `innerText`.
- **Virtualised lists.** Very long conversations may not have all messages mounted in the DOM. Scroll to the top of the conversation first to force every turn to render.
- **Selector drift.** claude.ai is a React app and may rename class names between deployments. If the alert reports `0 messages`, open DevTools → Console and run:

  ```javascript
  console.log('user-message:', document.querySelectorAll('[data-testid="user-message"]').length);
  console.log('font-user-message:', document.querySelectorAll('div.font-user-message').length);
  console.log('font-claude-message:', document.querySelectorAll('div.font-claude-message').length);
  ```

  to inspect which selectors still match, then update the bookmarklet accordingly.

## Verification

Before relying on the bookmarklet for ingestion, sanity-check the output against the visible conversation:

- Message count in the alert should equal `(user turns) + (assistant turns)`.
- The last message in the transcript should match the last message visible in the UI.
