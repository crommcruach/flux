# Planned Features

## Future Development Roadmap

### Visualization
- 3D Visualizer
- 2D Visual Mapping Feature
- Update Thumbnails

### Control Systems
- DMX Control
- MIDI Support

### Infrastructure
- Cluster Support

### Node-Based / Code Dual-Mode Editor

**Concept:** A bidirectional programming interface that runs entirely in the web UI. The user edits ISF/GLSL code or builds a node graph in the browser; the finished shader/plugin is sent to the backend via API where it is registered as a `PluginBase` plugin and enters the normal pipeline.

**Architecture (everything before the API call is browser-only):**

```
Browser (node-editor.html)
│
├─ Node graph (LiteGraph.js)  ◄──────────────────────────────┐
│     drag-and-drop, plugin-contributed node types            │  bidirectional
│                                                             │  translation
├─ Code editor (Monaco, ISF/GLSL syntax)  ────────────────────┘
│     user writes / AI patches ISF code
│
│  [Save / Compile]
│
└─ POST /api/plugins/register  { name, code, format:"isf" }
         │
         ▼
   Backend: parse ISF header → create PluginBase subclass
   → register as GENERATOR/EFFECT → live in pipeline
```

- **Web-only editing:** all node graph and code work happens in the browser with no round-trips during editing; only the final `POST` touches the backend
- **ISF as the shared language:** ISF 2.0 is the canonical format — the node graph serialises to ISF, and ISF parses back to a node graph; pure GLSL is an import path only
- **Node view** (end-users / VJs): drag-and-drop graph built with **LiteGraph.js**; node types contributed by small JS + Python plugin pairs
- **Code view** (AI / pros): Monaco editor with ISF/GLSL syntax; editing the code re-parses the ISF header and re-wires the node graph live
- **Bidirectional translation:** nodes → ISF code and ISF code → nodes, sync on every change
- **AI integration:** AI operates on the plain ISF code in the Monaco editor; result is reflected back into the node graph automatically
- **Unknown-code placeholder node:** if a code snippet has no matching node plugin it is rendered as a grey `[Unknown Block]` placeholder node
  - Raw source stored verbatim inside the placeholder, shown as read-only preview
  - Ports inferred from function signature so the graph stays wired
  - Executes original code unchanged at runtime
  - User can "promote" placeholder → auto-scaffolds a real node plugin file
  - AI can inspect and suggest/generate the missing node definition
- **Plugin-based node registry:** each node type is a small plugin — a `.js` file for the frontend (LiteGraph node definition) paired with a Python `PluginBase` file for the backend
  - Drop files into `plugins/nodes/` and they appear in the palette automatically
  - Community / third-party nodes install the same way; user nodes in `plugins/nodes/user/` are never overwritten on update
- **Use cases:**
  - Beginners build a chain visually → inspect generated ISF code to learn
  - AI reviews / refactors ISF code → updated node graph shown live
  - Pros write ISF directly → share as a node preset for non-coders
