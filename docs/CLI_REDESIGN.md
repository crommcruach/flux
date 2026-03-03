# CLI Command Redesign

## Overview

This document maps all API endpoints that receive input from the frontend to CLI commands.
The design follows a hierarchical structure: `main-command subcommand [options]`

## Design Principles

1. **Hierarchical Structure**: Commands are organized by domain (player, session, output, etc.)
2. **Consistency**: Similar operations use similar patterns across domains
3. **Player IDs**: Commands support `-p/--player` flag for `video` or `artnet` player
4. **Short & Long Options**: All commands support both short (`-v`) and long (`--value`) options
5. **Auto-completion friendly**: Predictable structure for tab completion

---

## Command Structure

```
flux <domain> <action> [options]
```

### Domains
- `player` - Player control & playback
- `clip` - Clip management
- `effect` - Effect management
- `layer` - Layer compositing
- `output` - Output routing (Art-Net, NDI, etc.)
- `playlist` - Playlist management
- `session` - Session state management
- `config` - Configuration management
- `audio` - Audio analysis & sequencer
- `sequence` - Parameter sequences
- `content` - File & project management
- `mapper` - LED mapping tools
- `debug` - Debug & logging
- `system` - System utilities

---

## 1. PLAYER COMMANDS

### 1.1 Playback Control

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `POST /api/player/<player_id>/play` | `player play [-p <player>]` | `player play -p video` |
| `POST /api/player/<player_id>/pause` | `player pause [-p <player>]` | `player pause -p artnet` |
| `POST /api/player/<player_id>/stop` | `player stop [-p <player>]` | `player stop` |
| `POST /api/player/<player_id>/clear` | `player clear [-p <player>]` | `player clear -p video` |
| `POST /api/player/<player_id>/next` | `player next [-p <player>]` | `player next` |
| `POST /api/player/<player_id>/previous` | `player prev [-p <player>]` | `player prev` |
| `GET /api/player/<player_id>/status` | `player status [-p <player>]` | `player status -p video` |

**Suggested CLI Commands:**
```bash
# Playback
player play                    # Start playback (current player)
player play -p video           # Start video player
player play -p artnet          # Start artnet player
player play --all              # Start all players

player pause                   # Pause current player
player pause -p video          # Pause video player

player stop                    # Stop current player
player stop --all              # Stop all players

player clear                   # Clear current player
player clear --all             # Clear all players

# Navigation
player next                    # Next clip in playlist
player prev                    # Previous clip in playlist

# Status
player status                  # Show current player status
player status -p video         # Show video player status
player status --all            # Show all players status
```

### 1.2 Clip Loading

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `POST /api/player/<player_id>/clip/load` | `clip load <path> [-p <player>]` | `clip load video.mp4 -p video` |
| `GET /api/player/<player_id>/clip/current` | `clip current [-p <player>]` | `clip current` |

**Suggested CLI Commands:**
```bash
# Load clips
clip load video.mp4            # Load video to current player
clip load video.mp4 -p video   # Load to video player
clip load video.mp4 -p artnet  # Load to artnet player
clip load video.mp4 --all      # Load to all players

# Get current clip
clip current                   # Show current clip info
clip current -p video          # Show video player's clip
```

### 1.3 Player Settings

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `POST /api/player/video/settings` | `player settings [-p <player>] [options]` | `player settings -p video --brightness 75` |
| `GET /api/player/video/settings` | `player settings [-p <player>]` | `player settings -p video` |
| `POST /api/brightness` (legacy) | `player set brightness <value>` | `player set brightness 75` |
| `POST /api/speed` (legacy) | `player set speed <value>` | `player set speed 1.5` |
| `POST /api/fps` (legacy) | `player set fps <value>` | `player set fps 30` |
| `POST /api/loop` (legacy) | `player set loop <value>` | `player set loop 5` |

**Suggested CLI Commands:**
```bash
# Get settings
player settings                # Show current player settings
player settings -p video       # Show video player settings

# Set parameters (individual)
player set brightness 75       # Set brightness (0-100)
player set speed 1.5           # Set playback speed
player set fps 30              # Set FPS limit
player set loop 5              # Set loop count (0 = infinite)
player set hue 180             # Set hue rotation

# Set parameters (batch)
player settings -p video --brightness 75 --speed 1.5 --fps 30
```

### 1.4 Master/Slave Sync

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `POST /api/player/<player_id>/set_master` | `player master <player_id> [--sync-mode <mode>]` | `player master video --sync-mode timeline` |
| `GET /api/player/sync_status` | `player sync status` | `player sync status` |

**Suggested CLI Commands:**
```bash
# Set master player
player master video            # Set video player as master
player master artnet           # Set artnet player as master
player master video --sync-mode timeline    # Timeline sync
player master video --sync-mode transport   # Transport sync

# Get sync status
player sync status             # Show current sync configuration
```

---

## 2. CLIP COMMANDS

### 2.1 Clip Effects

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/player/<player_id>/clip/<clip_id>/effects` | `clip effects <clip_id> [-p <player>]` | `clip effects abc123 -p video` |
| `POST /api/player/<player_id>/clip/<clip_id>/effects/add` | `clip effect add <clip_id> <plugin_id> [-p <player>]` | `clip effect add abc123 blur` |
| `PUT /api/player/<player_id>/clip/<clip_id>/effects/<index>/parameter` | `clip effect set <clip_id> <index> <param> <value>` | `clip effect set abc123 0 radius 10` |
| `DELETE /api/player/<player_id>/clip/<clip_id>/effects/<index>` | `clip effect remove <clip_id> <index>` | `clip effect remove abc123 0` |
| `POST /api/player/<player_id>/clip/<clip_id>/effects/clear` | `clip effect clear <clip_id>` | `clip effect clear abc123` |
| `POST /api/player/<player_id>/clip/<clip_id>/effects/<index>/toggle` | `clip effect toggle <clip_id> <index>` | `clip effect toggle abc123 0` |

**Suggested CLI Commands:**
```bash
# List effects
clip effects abc123            # Show effects for clip
clip effects abc123 -p video   # Show for specific player

# Add effect
clip effect add abc123 blur    # Add blur effect to clip
clip effect add abc123 blur -p video

# Update effect parameter
clip effect set abc123 0 radius 10      # Set parameter of effect at index 0
clip effect set abc123 0 radius 10 -p video

# Toggle effect
clip effect toggle abc123 0    # Enable/disable effect at index 0

# Remove effect
clip effect remove abc123 0    # Remove effect at index 0

# Clear all effects
clip effect clear abc123       # Remove all effects from clip
```

### 2.2 Clip Generator Parameters

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `POST /api/player/<player_id>/clip/<clip_id>/generator/parameter` | `clip generator set <clip_id> <param> <value>` | `clip generator set abc123 speed 2.0` |

**Suggested CLI Commands:**
```bash
# Set generator parameter
clip generator set abc123 speed 2.0         # Set generator parameter
clip generator set abc123 speed 2.0 -p video
```

---

## 3. EFFECT COMMANDS (Global Player Effects)

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/player/<player_id>/effects` | `effect list [-p <player>]` | `effect list -p video` |
| `POST /api/player/<player_id>/effects/add` | `effect add <plugin_id> [-p <player>]` | `effect add blur -p video` |
| `PUT /api/player/<player_id>/effects/<index>/parameter` | `effect set <index> <param> <value> [-p <player>]` | `effect set 0 radius 10 -p video` |
| `DELETE /api/player/<player_id>/effects/<index>` | `effect remove <index> [-p <player>]` | `effect remove 0 -p video` |
| `POST /api/player/<player_id>/effects/clear` | `effect clear [-p <player>]` | `effect clear -p video` |
| `POST /api/player/<player_id>/effects/<index>/toggle` | `effect toggle <index> [-p <player>]` | `effect toggle 0 -p video` |

**Suggested CLI Commands:**
```bash
# List effects
effect list                    # Show all effects on current player
effect list -p video           # Show effects on video player

# Add effect
effect add blur                # Add blur effect to current player
effect add blur -p video       # Add to video player
effect add blur -p artnet      # Add to artnet player

# Set effect parameter
effect set 0 radius 10         # Set parameter on effect at index 0
effect set 0 radius 10 -p video

# Toggle effect
effect toggle 0                # Enable/disable effect at index 0
effect toggle 0 -p video

# Remove effect
effect remove 0                # Remove effect at index 0
effect remove 0 -p artnet

# Clear all effects
effect clear                   # Remove all effects from current player
effect clear -p video          # Clear video player effects
effect clear --all             # Clear all players
```

---

## 4. LAYER COMMANDS

### 4.1 Player Layers

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/player/<player_id>/layers` | `layer list [-p <player>]` | `layer list -p video` |
| `POST /api/player/<player_id>/layers/add` | `layer add [-p <player>] [options]` | `layer add -p video --blend multiply` |
| `DELETE /api/player/<player_id>/layers/<layer_id>` | `layer remove <layer_id> [-p <player>]` | `layer remove 1 -p video` |
| `PATCH /api/player/<player_id>/layers/<layer_id>` | `layer update <layer_id> [options] [-p <player>]` | `layer update 1 --opacity 0.5` |
| `PUT /api/player/<player_id>/layers/reorder` | `layer reorder <layer_ids> [-p <player>]` | `layer reorder 2,1,0` |
| `POST /api/player/<player_id>/layers/<layer_id>/clip/load` | `layer load <layer_id> <video_path> [-p <player>]` | `layer load 1 video.mp4` |

**Suggested CLI Commands:**
```bash
# List layers
layer list                     # Show all layers on current player
layer list -p video            # Show layers on video player

# Add layer
layer add                      # Add new layer
layer add -p video             # Add to video player
layer add --blend multiply --opacity 0.8    # Add with settings

# Update layer
layer update 1 --opacity 0.5   # Update opacity of layer 1
layer update 1 --blend screen  # Update blend mode
layer update 1 --opacity 0.5 --blend add

# Remove layer
layer remove 1                 # Remove layer 1
layer remove 1 -p video

# Reorder layers
layer reorder 2,1,0            # Reorder layers (bottom to top)

# Load clip to layer
layer load 1 video.mp4         # Load video to layer 1
layer load 1 video.mp4 -p video
```

### 4.2 Clip Layers

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/clips/<clip_id>/layers` | `clip layers <clip_id>` | `clip layers abc123` |
| `POST /api/clips/<clip_id>/layers/add` | `clip layer add <clip_id> [options]` | `clip layer add abc123 --source generator` |
| `DELETE /api/clips/<clip_id>/layers/<layer_id>` | `clip layer remove <clip_id> <layer_id>` | `clip layer remove abc123 1` |
| `PATCH /api/clips/<clip_id>/layers/<layer_id>` | `clip layer update <clip_id> <layer_id> [options]` | `clip layer update abc123 1 --opacity 0.5` |
| `PUT /api/clips/<clip_id>/layers/reorder` | `clip layer reorder <clip_id> <layer_ids>` | `clip layer reorder abc123 2,1,0` |

**Suggested CLI Commands:**
```bash
# List clip layers
clip layers abc123             # Show layers for clip

# Add layer to clip
clip layer add abc123          # Add layer to clip
clip layer add abc123 --source generator --plugin rainbow

# Update clip layer
clip layer update abc123 1 --opacity 0.5
clip layer update abc123 1 --blend multiply

# Remove clip layer
clip layer remove abc123 1     # Remove layer from clip

# Reorder clip layers
clip layer reorder abc123 2,1,0
```

---

## 5. OUTPUT COMMANDS

### 5.1 Output Routing

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/outputs/<player>` | `output list [-p <player>]` | `output list -p artnet` |
| `POST /api/outputs/<player>` | `output add [-p <player>] <type> [options]` | `output add -p artnet artnet --ip 192.168.1.11` |
| `POST /api/outputs/<player>/<output_id>/enable` | `output enable <output_id> [-p <player>]` | `output enable out1` |
| `POST /api/outputs/<player>/<output_id>/disable` | `output disable <output_id> [-p <player>]` | `output disable out1` |
| `DELETE /api/outputs/<player>/<output_id>` | `output remove <output_id> [-p <player>]` | `output remove out1` |
| `PUT /api/outputs/<player>/<output_id>/source` | `output source <output_id> <source> [-p <player>]` | `output source out1 video` |
| `GET /api/outputs/types` | `output types` | `output types` |
| `GET /api/monitors` | `output monitors` | `output monitors` |

**Suggested CLI Commands:**
```bash
# List outputs
output list                    # Show all outputs
output list -p artnet          # Show outputs for artnet player
output list -p video           # Show outputs for video player

# List available types/monitors
output types                   # Show available output types
output monitors                # Show available monitors

# Add output
output add artnet --ip 192.168.1.11 --universe 0
output add artnet --ip 192.168.1.11 -u 0 -p artnet
output add ndi --name "Output 1"
output add window --monitor 1

# Enable/disable output
output enable out1             # Enable output
output disable out1            # Disable output
output enable out1 -p artnet

# Change output source
output source out1 video       # Set output source to video player
output source out1 artnet      # Set output source to artnet player

# Remove output
output remove out1             # Remove output
output remove out1 -p artnet
```

### 5.2 Art-Net Settings

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/player/artnet/settings` | `output artnet settings` | `output artnet settings` |
| `POST /api/player/artnet/settings` | `output artnet set [options]` | `output artnet set --ip 192.168.1.11` |
| `GET /api/artnet/resolution` | `output artnet resolution` | `output artnet resolution` |
| `POST /api/artnet/resolution` | `output artnet resolution <width> <height>` | `output artnet resolution 100 100` |
| `POST /api/blackout` (legacy) | `output artnet blackout` | `output artnet blackout` |
| `POST /api/test` (legacy) | `output artnet test [<color>]` | `output artnet test red` |
| `GET /api/local_ips` | `output artnet ips` | `output artnet ips` |

**Suggested CLI Commands:**
```bash
# Art-Net settings
output artnet settings         # Show current Art-Net settings
output artnet set --ip 192.168.1.11    # Set target IP
output artnet set --ip 192.168.1.11 --universe 0

# Resolution
output artnet resolution       # Show current resolution
output artnet resolution 100 100    # Set resolution (width x height)

# Testing
output artnet blackout         # Send blackout (all channels = 0)
output artnet test            # Send test pattern (red)
output artnet test red        # Send red test pattern
output artnet test gradient   # Send gradient pattern

# Network info
output artnet ips             # Show available local IPs
```

### 5.3 Points Management (Legacy)

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/points/list` | `output points list` | `output points list` |
| `POST /api/points/switch` | `output points load <filename>` | `output points load points.json` |
| `POST /api/points/reload` | `output points reload` | `output points reload` |
| `POST /api/points/validate` | `output points validate [<filename>]` | `output points validate points.json` |
| `GET /api/points/current` | `output points current` | `output points current` |

**Suggested CLI Commands:**
```bash
# List points files
output points list             # Show all points files

# Load points
output points load points.json # Switch to different points file
output points reload           # Reload current points file

# Validate
output points validate points.json    # Validate specific file
output points validate                # Validate current file

# Current
output points current          # Show current points file info
```

---

## 6. PLAYLIST COMMANDS

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/playlists/list` | `playlist list` | `playlist list` |
| `POST /api/playlists/create` | `playlist create <name>` | `playlist create "My Playlist"` |
| `DELETE /api/playlists/<playlist_id>` | `playlist delete <playlist_id>` | `playlist delete pl123` |
| `PUT /api/playlists/<playlist_id>/rename` | `playlist rename <playlist_id> <new_name>` | `playlist rename pl123 "New Name"` |
| `POST /api/playlists/activate` | `playlist activate <playlist_id>` | `playlist activate pl123` |
| `POST /api/playlists/view` | `playlist view <playlist_id>` | `playlist view pl123` |
| `GET /api/playlists/<playlist_id>` | `playlist show <playlist_id>` | `playlist show pl123` |
| `POST /api/playlists/save-state` | `playlist save` | `playlist save` |
| `POST /api/playlists/update_player` | `playlist update` | `playlist update` |
| `POST /api/playlists/<playlist_id>/preview-clip` | `playlist preview <playlist_id> <clip_index>` | `playlist preview pl123 0` |
| `POST /api/playlists/<playlist_id>/takeover-preview/start` | `playlist takeover start <playlist_id>` | `playlist takeover start pl123` |
| `POST /api/playlists/takeover-preview/stop` | `playlist takeover stop` | `playlist takeover stop` |
| `GET /api/playlists/takeover-preview/status` | `playlist takeover status` | `playlist takeover status` |

**Suggested CLI Commands:**
```bash
# List playlists
playlist list                  # Show all playlists

# Create playlist
playlist create "My Playlist"  # Create new playlist

# Delete playlist
playlist delete pl123          # Delete playlist

# Rename playlist
playlist rename pl123 "New Name"    # Rename playlist

# Activate/view playlist
playlist activate pl123        # Activate playlist (make it master)
playlist view pl123            # View playlist (edit without activating)

# Show playlist
playlist show pl123            # Show playlist details

# Save/update
playlist save                  # Save current state
playlist update                # Update viewed playlist with player state

# Preview
playlist preview pl123 0       # Preview clip at index 0
playlist takeover start pl123  # Start takeover preview
playlist takeover stop         # Stop takeover preview
playlist takeover status       # Get takeover status
```

---

## 7. TRANSITION COMMANDS

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/transitions/list` | `transition list` | `transition list` |
| `POST /api/player/<player_id>/transition/config` | `transition set [-p <player>] [options]` | `transition set --type fade --duration 1.0` |
| `GET /api/player/<player_id>/transition/status` | `transition status [-p <player>]` | `transition status` |

**Suggested CLI Commands:**
```bash
# List available transitions
transition list                # Show all available transitions

# Configure transition
transition set --type fade --duration 1.0
transition set --type crossfade --duration 2.0 -p video
transition set --type wipe --duration 1.5 --direction left

# Get status
transition status              # Show current transition config
transition status -p artnet
```

---

## 8. SESSION COMMANDS

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/session/state` | `session show` | `session show` |
| `POST /api/session/state` | `session update [options]` | `session update --key value` |
| `POST /api/session/snapshot` | `session snapshot [<name>]` | `session snapshot "Backup 1"` |
| `GET /api/session/snapshots` | `session snapshots` | `session snapshots` |
| `POST /api/session/snapshot/restore` | `session restore <snapshot_name>` | `session restore "Backup 1"` |
| `POST /api/session/snapshot/delete` | `session snapshot delete <snapshot_name>` | `session snapshot delete "Old"` |
| `POST /api/session/save` | `session save <filename>` | `session save project.json` |
| `GET /api/session/list` | `session list` | `session list` |
| `POST /api/session/restore` | `session load <filename>` | `session load project.json` |
| `POST /api/session/delete` | `session delete <filename>` | `session delete old.json` |
| `GET /api/session/download` | `session download` | `session download` |
| `POST /api/session/upload` | `session upload <file>` | `session upload session.json` |
| `POST /api/session/editor` | `session editor [options]` | `session editor --width 1920` |
| `GET /api/session/mapper` | `session mapper` | `session mapper` |
| `POST /api/session/mapper` | `session mapper [options]` | `session mapper --setting value` |

**Suggested CLI Commands:**
```bash
# Show/update state
session show                   # Display current session state
session update --key value     # Update session state

# Snapshots (in-memory)
session snapshot "Backup 1"    # Create snapshot
session snapshots              # List all snapshots
session restore "Backup 1"     # Restore snapshot
session snapshot delete "Old"  # Delete snapshot

# File operations
session save project.json      # Save session to file
session list                   # List saved sessions
session load project.json      # Load session from file
session delete old.json        # Delete saved session

# Import/export
session download               # Download session as file
session upload session.json    # Upload session file

# Editor/Mapper state
session editor --width 1920 --height 1080    # Update editor state
session mapper                 # Show mapper state
session mapper --setting value # Update mapper state
```

---

## 9. CONFIG COMMANDS

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/config` | `config show` | `config show` |
| `POST /api/config` | `config set [options]` | `config set --key value` |
| `POST /api/config/validate` | `config validate [<file>]` | `config validate config.json` |
| `POST /api/config/restore` | `config restore` | `config restore` |
| `GET /api/config/schema` | `config schema` | `config schema` |
| `GET /api/config/default` | `config default` | `config default` |
| `GET /api/config/frontend` | `config frontend` | `config frontend` |

**Suggested CLI Commands:**
```bash
# Show config
config show                    # Show current configuration
config frontend                # Show frontend config

# Update config
config set --key value         # Set config value
config set --artnet.ip 192.168.1.11
config set --video.fps 30

# Validate
config validate                # Validate current config
config validate config.json    # Validate specific file

# Restore
config restore                 # Restore from backup

# Schema & defaults
config schema                  # Show config schema
config default                 # Show default configuration
```

---

## 10. AUDIO COMMANDS

### 10.1 BPM Detection

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `POST /api/bpm/start` | `audio bpm start` | `audio bpm start` |
| `POST /api/bpm/pause` | `audio bpm pause` | `audio bpm pause` |
| `POST /api/bpm/stop` | `audio bpm stop` | `audio bpm stop` |
| `POST /api/bpm/manual` | `audio bpm set <value>` | `audio bpm set 120` |
| `GET /api/bpm/status` | `audio bpm status` | `audio bpm status` |

**Suggested CLI Commands:**
```bash
# BPM detection control
audio bpm start                # Start BPM detection
audio bpm pause                # Pause BPM detection
audio bpm stop                 # Stop BPM detection

# Manual BPM
audio bpm set 120              # Set manual BPM

# Status
audio bpm status               # Show BPM status and current value
```

### 10.2 Sequencer

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `POST /api/sequencer/mode` | `audio sequencer mode <enabled>` | `audio sequencer mode on` |
| `POST /api/sequencer/upload` | `audio sequencer upload <file>` | `audio sequencer upload track.mp3` |
| `POST /api/sequencer/load` | `audio sequencer load <filename>` | `audio sequencer load track.mp3` |
| `GET /api/sequencer/files` | `audio sequencer list` | `audio sequencer list` |
| `POST /api/sequencer/play` | `audio sequencer play` | `audio sequencer play` |
| `POST /api/sequencer/pause` | `audio sequencer pause` | `audio sequencer pause` |
| `POST /api/sequencer/stop` | `audio sequencer stop` | `audio sequencer stop` |
| `POST /api/sequencer/seek` | `audio sequencer seek <time>` | `audio sequencer seek 30.5` |
| `GET /api/sequencer/status` | `audio sequencer status` | `audio sequencer status` |
| `GET /api/sequencer/timeline` | `audio sequencer timeline` | `audio sequencer timeline` |
| `POST /api/sequencer/splits/add` | `audio sequencer split add <time>` | `audio sequencer split add 10.5` |
| `POST /api/sequencer/splits/remove` | `audio sequencer split remove <index>` | `audio sequencer split remove 0` |
| `POST /api/sequencer/splits/clear` | `audio sequencer split clear` | `audio sequencer split clear` |
| `POST /api/sequencer/slot/clip` | `audio sequencer slot <slot_index> <clip_index>` | `audio sequencer slot 0 5` |

**Suggested CLI Commands:**
```bash
# Sequencer mode
audio sequencer mode on        # Enable sequencer as master
audio sequencer mode off       # Disable sequencer

# File management
audio sequencer list           # List audio files
audio sequencer upload track.mp3    # Upload audio file
audio sequencer load track.mp3      # Load audio file

# Playback
audio sequencer play           # Start playback
audio sequencer pause          # Pause playback
audio sequencer stop           # Stop playback
audio sequencer seek 30.5      # Seek to time (seconds)

# Status & timeline
audio sequencer status         # Show sequencer status
audio sequencer timeline       # Show timeline with splits

# Splits
audio sequencer split add 10.5      # Add split at 10.5 seconds
audio sequencer split remove 0      # Remove split at index
audio sequencer split clear         # Remove all splits

# Slot mapping
audio sequencer slot 0 5       # Map clip index 5 to slot 0
```

---

## 11. SEQUENCE COMMANDS (Parameter Sequences)

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/sequences` | `sequence list` | `sequence list` |
| `GET /api/sequences/<sequence_id>` | `sequence show <id>` | `sequence show seq123` |
| `POST /api/sequences` | `sequence create [options]` | `sequence create --clip abc123` |
| `PUT /api/sequences/<sequence_id>` | `sequence update <id> [options]` | `sequence update seq123 --enabled true` |
| `DELETE /api/sequences/<sequence_id>` | `sequence delete <id>` | `sequence delete seq123` |
| `POST /api/sequences/<sequence_id>/keyframes` | `sequence keyframe add <id> <time> <value>` | `sequence keyframe add seq123 0 100` |
| `DELETE /api/sequences/<sequence_id>/keyframes/<index>` | `sequence keyframe remove <id> <index>` | `sequence keyframe remove seq123 0` |
| `POST /api/sequences/record/start` | `sequence record start` | `sequence record start` |
| `POST /api/sequences/record/stop` | `sequence record stop` | `sequence record stop` |

**Suggested CLI Commands:**
```bash
# List sequences
sequence list                  # Show all sequences

# Create/show sequence
sequence create --clip abc123 --parameter brightness --audio-feature rms
sequence show seq123           # Show sequence details

# Update sequence
sequence update seq123 --enabled true
sequence update seq123 --mode multiply

# Delete sequence
sequence delete seq123         # Delete sequence

# Keyframes
sequence keyframe add seq123 0 100      # Add keyframe
sequence keyframe remove seq123 0       # Remove keyframe

# Recording
sequence record start          # Start recording parameter changes
sequence record stop           # Stop recording
```

---

## 12. CONTENT COMMANDS

### 12.1 File Management

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/files/tree` | `content tree` | `content tree` |
| `GET /api/files/videos` | `content list` | `content list` |
| `GET /api/files/thumbnail/<path>` | `content thumbnail <path>` | `content thumbnail video.mp4` |
| `POST /api/files/thumbnails/batch` | `content thumbnail batch <paths>` | `content thumbnail batch *.mp4` |
| `GET /api/files/thumbnails/stats` | `content thumbnail stats` | `content thumbnail stats` |
| `POST /api/files/thumbnails/cleanup` | `content thumbnail cleanup` | `content thumbnail cleanup` |
| `DELETE /api/files/delete` | `content delete <path>` | `content delete video.mp4` |

**Suggested CLI Commands:**
```bash
# Browse files
content tree                   # Show file tree
content list                   # List all videos

# Thumbnails
content thumbnail video.mp4    # Generate thumbnail for video
content thumbnail batch *.mp4  # Generate batch thumbnails
content thumbnail stats        # Show thumbnail statistics
content thumbnail cleanup      # Clean up unused thumbnails

# Delete files
content delete video.mp4       # Delete file
```

### 12.2 Projects

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/projects` | `project list` | `project list` |
| `POST /api/projects/save` | `project save <name>` | `project save "My Project"` |
| `GET /api/projects/load/<filename>` | `project load <filename>` | `project load project.json` |
| `DELETE /api/projects/delete/<filename>` | `project delete <filename>` | `project delete old.json` |
| `GET /api/projects/download/<filename>` | `project download <filename>` | `project download project.json` |

**Suggested CLI Commands:**
```bash
# Project management
project list                   # List all projects
project save "My Project"      # Save current project
project load project.json      # Load project
project delete old.json        # Delete project
project download project.json  # Download project file
```

### 12.3 Plugins

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/plugins/list` | `plugin list` | `plugin list` |
| `GET /api/plugins/<plugin_id>/metadata` | `plugin info <plugin_id>` | `plugin info blur` |
| `GET /api/plugins/<plugin_id>/parameters` | `plugin params <plugin_id>` | `plugin params blur` |
| `POST /api/plugins/<plugin_id>/load` | `plugin load <plugin_id>` | `plugin load blur` |
| `POST /api/plugins/<plugin_id>/unload` | `plugin unload <plugin_id>` | `plugin unload blur` |
| `POST /api/plugins/<plugin_id>/parameters/<param>` | `plugin set <plugin_id> <param> <value>` | `plugin set blur radius 10` |
| `GET /api/plugins/stats` | `plugin stats` | `plugin stats` |
| `POST /api/plugins/reload` | `plugin reload` | `plugin reload` |

**Suggested CLI Commands:**
```bash
# List plugins
plugin list                    # Show all plugins
plugin stats                   # Show plugin statistics

# Plugin info
plugin info blur               # Show plugin metadata
plugin params blur             # Show plugin parameters

# Load/unload
plugin load blur               # Load plugin
plugin unload blur             # Unload plugin
plugin reload                  # Reload all plugins

# Set parameters (global defaults)
plugin set blur radius 10      # Set global default parameter
```

### 12.4 Converter

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/converter/status` | `convert status` | `convert status` |
| `GET /api/converter/formats` | `convert formats` | `convert formats` |
| `POST /api/converter/info` | `convert info <file>` | `convert info video.mp4` |
| `POST /api/converter/convert` | `convert <input> [options]` | `convert video.mp4 --output out.mp4` |
| `POST /api/converter/batch` | `convert batch <pattern> [options]` | `convert batch *.mp4 --codec hap` |
| `POST /api/converter/upload` | `convert upload <file>` | `convert upload video.mp4` |
| `GET /api/converter/canvas-size` | `convert canvas` | `convert canvas` |

**Suggested CLI Commands:**
```bash
# Converter info
convert status                 # Show conversion status
convert formats                # Show supported formats
convert canvas                 # Show canvas size

# File info
convert info video.mp4         # Get video information

# Convert
convert video.mp4 --output out.mp4 --codec hap
convert video.mp4 -o out.mp4 -c hap -q high
convert batch *.mp4 --codec hap --quality high

# Upload
convert upload video.mp4       # Upload file for conversion
```

---

## 13. MAPPER COMMANDS

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `POST /api/mapper/simple-test` | `mapper test simple` | `mapper test simple` |
| `POST /api/mapper/start-sequence` | `mapper test sequence start` | `mapper test sequence start` |
| `POST /api/mapper/stop-sequence` | `mapper test sequence stop` | `mapper test sequence stop` |
| `POST /api/mapper/test-single-led` | `mapper test led <x> <y>` | `mapper test led 10 20` |
| `POST /api/mapper/network-diagnostics` | `mapper diagnostics` | `mapper diagnostics` |

**Suggested CLI Commands:**
```bash
# LED mapping tests
mapper test simple             # Simple test pattern
mapper test sequence start     # Start LED sequence test
mapper test sequence stop      # Stop LED sequence test
mapper test led 10 20          # Test single LED at position

# Diagnostics
mapper diagnostics             # Run network diagnostics
```

---

## 14. DEBUG COMMANDS

### 14.1 Debug Categories

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/debug/categories` | `debug categories` | `debug categories` |
| `POST /api/debug/categories/enable` | `debug category enable <category>` | `debug category enable effects` |
| `POST /api/debug/categories/disable` | `debug category disable <category>` | `debug category disable effects` |
| `POST /api/debug/categories/toggle` | `debug category toggle <category>` | `debug category toggle effects` |

**Suggested CLI Commands:**
```bash
# Debug categories
debug categories               # List all debug categories
debug category enable effects  # Enable category
debug category disable effects # Disable category
debug category toggle effects  # Toggle category
```

### 14.2 Debug Modules

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/debug/modules` | `debug modules` | `debug modules` |
| `POST /api/debug/modules/enable` | `debug module enable <module>` | `debug module enable player` |
| `POST /api/debug/modules/disable` | `debug module disable <module>` | `debug module disable player` |

**Suggested CLI Commands:**
```bash
# Debug modules
debug modules                  # List all modules
debug module enable player     # Enable module debugging
debug module disable player    # Disable module debugging
```

### 14.3 Logging

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/logs` | `log show` | `log show` |
| `GET /api/logs/files` | `log files` | `log files` |
| `POST /api/logs/clear` | `log clear` | `log clear` |
| `POST /api/logs/js-error` | (frontend only) | - |
| `POST /api/logs/js-log` | (frontend only) | - |

**Suggested CLI Commands:**
```bash
# Logs
log show                       # Show recent log entries
log files                      # List log files
log clear                      # Clear log buffer
```

---

## 15. SYSTEM COMMANDS

### 15.1 Performance

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/performance/metrics` | `perf metrics` | `perf metrics` |
| `POST /api/performance/reset` | `perf reset` | `perf reset` |
| `POST /api/performance/toggle` | `perf toggle` | `perf toggle` |

**Suggested CLI Commands:**
```bash
# Performance monitoring
perf metrics                   # Show performance metrics
perf reset                     # Reset metrics
perf toggle                    # Toggle performance monitoring
```

### 15.2 Console

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/console/log` | `console log` | `console log` |
| `POST /api/console/command` | (internal - executes CLI commands) | - |
| `POST /api/console/clear` | `console clear` | `console clear` |
| `GET /api/console/help` | `console help` | `console help` |

**Suggested CLI Commands:**
```bash
# Console (web interface)
console log                    # Show console log
console clear                  # Clear console
console help                   # Show console help
```

### 15.3 Background Images

| API Endpoint | CLI Command | Example |
|--------------|-------------|---------|
| `GET /api/backgrounds` | `content backgrounds` | `content backgrounds` |
| `POST /api/backgrounds/upload` | `content background upload <file>` | `content background upload bg.jpg` |
| `DELETE /api/backgrounds/<filename>` | `content background delete <filename>` | `content background delete bg.jpg` |
| `GET /api/backgrounds/<filename>` | `content background get <filename>` | `content background get bg.jpg` |

**Suggested CLI Commands:**
```bash
# Background images
content backgrounds            # List backgrounds
content background upload bg.jpg    # Upload background
content background delete bg.jpg    # Delete background
content background get bg.jpg       # Get background info
```

---

## 16. LEGACY/DEPRECATED COMMANDS

These endpoints are being phased out but included for reference:

| API Endpoint | CLI Command | Status |
|--------------|-------------|--------|
| `GET /api/cache/stats` | `cache stats` | DEPRECATED - RGB caching removed |
| `POST /api/cache/clear` | `cache clear` | DEPRECATED - RGB caching removed |
| `GET /api/scripts` | `script list` | DEPRECATED - Use plugins instead |
| `POST /api/load_script` | `script load <name>` | DEPRECATED - Use plugins instead |

---

## IMPLEMENTATION NOTES

### Command Groups

Commands should be organized into logical groups for easier implementation:

```python
# src/modules/cli/commands/
player.py       # Player commands
clip.py         # Clip commands
effect.py       # Effect commands
layer.py        # Layer commands
output.py       # Output commands
playlist.py     # Playlist commands
transition.py   # Transition commands
session.py      # Session commands
config.py       # Config commands
audio.py        # Audio commands
sequence.py     # Sequence commands
content.py      # Content commands
project.py      # Project commands
plugin.py       # Plugin commands
mapper.py       # Mapper commands
debug.py        # Debug commands
system.py       # System commands
```

### Command Parser Structure

Use argparse with subparsers:

```python
import argparse

def create_parser():
    parser = argparse.ArgumentParser(prog='flux')
    subparsers = parser.add_subparsers(dest='domain')
    
    # Player commands
    player_parser = subparsers.add_parser('player')
    player_subparsers = player_parser.add_subparsers(dest='action')
    
    # player play
    play_parser = player_subparsers.add_parser('play')
    play_parser.add_argument('-p', '--player', choices=['video', 'artnet', 'all'])
    
    # player pause
    pause_parser = player_subparsers.add_parser('pause')
    pause_parser.add_argument('-p', '--player', choices=['video', 'artnet', 'all'])
    
    # ... more commands
    
    return parser
```

### Global Options

These options should be available for all commands:

```bash
-h, --help        # Show help
-v, --verbose     # Verbose output
-q, --quiet       # Quiet mode (errors only)
-j, --json        # JSON output
--no-color        # Disable colored output
```

### Output Formats

Support multiple output formats:

1. **Human-readable** (default): Formatted tables, colors
2. **JSON** (`--json`): Machine-readable
3. **Quiet** (`--quiet`): Only errors
4. **Verbose** (`--verbose`): Detailed information

### Environment Variables

Support environment variables for common options:

```bash
FLUX_PLAYER=video      # Default player
FLUX_OUTPUT_FORMAT=json # Default output format
FLUX_API_URL=http://localhost:5000  # API endpoint
```

### Auto-completion

Generate shell completion scripts for:
- Bash
- Zsh
- Fish
- PowerShell

### Error Handling

Consistent error codes:
```
0 - Success
1 - General error
2 - Invalid arguments
3 - API error
4 - Connection error
5 - File not found
```

---

## CLI USER EXPERIENCE FEATURES

This section covers advanced UX features that make the CLI intuitive and user-friendly.

**Quick Navigation:**
- [Tab Completion](#tab-completion) - Auto-complete commands, files, and IDs
- [Interactive Help](#interactive-help-system) - Contextual help as you type
- [Fuzzy Matching](#fuzzy-command-matching--did-you-mean) - Typo correction and suggestions
- [Inline Hints](#inline-command-hints) - Show available options
- [Command History](#command-history) - Persistent history across sessions
- [Smart Errors](#smart-error-messages) - Actionable error messages
- [Interactive Mode](#interactive-mode-with-prompt) - REPL-style interface
- [Progress Indicators](#progress-indicators) - Visual feedback for long operations
- [Colorized Output](#colorized-output) - Readable and accessible colors

### Tab Completion

#### Implementation Strategy

Use the `argcomplete` library for robust tab completion across shells:

```python
# src/modules/cli/completion.py
import argcomplete
import argparse

def setup_completion(parser):
    """Enable tab completion for the CLI."""
    argcomplete.autocomplete(parser)

def create_parser_with_completion():
    parser = create_parser()  # Your main parser
    argcomplete.autocomplete(parser)
    return parser
```

#### Shell-Specific Installation

**Bash:**
```bash
# Add to ~/.bashrc
eval "$(register-python-argcomplete flux)"

# Or generate completion script
flux --completion bash > /etc/bash_completion.d/flux
```

**Zsh:**
```bash
# Add to ~/.zshrc
autoload -U bashcompinit
bashcompinit
eval "$(register-python-argcomplete flux)"
```

**PowerShell:**
```powershell
# Add to $PROFILE
Register-ArgumentCompleter -Native -CommandName flux -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)
    $env:_ARGCOMPLETE = 1
    $env:_ARGCOMPLETE_SUPPRESS_SPACE = 1
    $env:COMP_LINE = $commandAst
    $env:COMP_POINT = $cursorPosition
    flux 2>&1 | ForEach-Object {
        [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_)
    }
}
```

**Fish:**
```fish
# Add to ~/.config/fish/completions/flux.fish
function __fish_flux_complete
    set -lx _ARGCOMPLETE 1
    set -lx _ARGCOMPLETE_FISH_PARSER 1
    set -lx COMP_LINE (commandline -p)
    set -lx COMP_POINT (string length (commandline -cp))
    flux 2>&1 | string split \t
end

complete -c flux -f -a '(__fish_flux_complete)'
```

#### Dynamic Completion

Complete commands with context-aware suggestions:

```python
# src/modules/cli/completers.py

def complete_player_id(prefix, parsed_args, **kwargs):
    """Complete player IDs (video, artnet)."""
    return ['video', 'artnet', 'all']

def complete_video_files(prefix, parsed_args, **kwargs):
    """Complete video file paths."""
    import glob
    video_dir = get_video_dir()
    pattern = os.path.join(video_dir, f'{prefix}*')
    files = glob.glob(pattern + '*.mp4') + glob.glob(pattern + '*.mov')
    return [os.path.basename(f) for f in files]

def complete_playlist_ids(prefix, parsed_args, **kwargs):
    """Complete playlist IDs from API."""
    try:
        response = api_call('/api/playlists/list')
        if response and response.get('success'):
            playlists = response.get('playlists', [])
            return [p['id'] for p in playlists]
    except:
        return []
    return []

def complete_plugin_ids(prefix, parsed_args, **kwargs):
    """Complete plugin IDs."""
    try:
        response = api_call('/api/plugins/list')
        if response:
            return [p['id'] for p in response.get('plugins', [])]
    except:
        return []
    return []

# Usage in parser
parser.add_argument('plugin_id', choices=[]).completer = complete_plugin_ids
parser.add_argument('video_path').completer = complete_video_files
parser.add_argument('-p', '--player').completer = complete_player_id
```

### Interactive Help System

#### Contextual Help Messages

Show helpful guidance when commands are incomplete or incorrect:

```python
# src/modules/cli/help.py

class SmartHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Custom help formatter with examples and tips."""
    
    def _format_action(self, action):
        # Add custom formatting with colors and examples
        help_text = super()._format_action(action)
        
        # Add examples for certain commands
        if hasattr(action, 'examples'):
            help_text += f"\n\n  {self._color('Examples:', 'cyan')}\n"
            for example in action.examples:
                help_text += f"    {self._color('$', 'green')} {example}\n"
        
        return help_text
    
    def _color(self, text, color):
        """Add ANSI color codes."""
        colors = {
            'red': '\033[91m',
            'green': '\033[92m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'cyan': '\033[96m',
            'reset': '\033[0m'
        }
        return f"{colors.get(color, '')}{text}{colors['reset']}"

# Add examples to commands
play_parser.examples = [
    'player play',
    'player play -p video',
    'player play --all'
]
```

#### Command-Specific Help with Usage Examples

```python
def show_command_help(domain, action=None):
    """Show detailed help for a command with examples."""
    
    help_data = {
        'player': {
            'description': 'Control video playback and player settings',
            'actions': {
                'play': {
                    'description': 'Start playback on one or more players',
                    'examples': [
                        'player play              # Start current player',
                        'player play -p video     # Start video player',
                        'player play --all        # Start all players'
                    ],
                    'options': {
                        '-p, --player': 'Specify player: video, artnet, or all',
                    }
                },
                'pause': {
                    'description': 'Pause playback',
                    'examples': ['player pause', 'player pause -p artnet']
                }
            },
            'examples': [
                '# Basic playback control',
                'player play',
                'player pause',
                'player stop',
                '',
                '# Player-specific control',
                'player play -p video',
                'player status -p artnet'
            ]
        }
    }
    
    if domain in help_data:
        data = help_data[domain]
        print(f"\n{colorize('Command:', 'cyan')} {domain}")
        print(f"{colorize('Description:', 'cyan')} {data['description']}\n")
        
        if action and action in data.get('actions', {}):
            action_data = data['actions'][action]
            print(f"{colorize('Action:', 'cyan')} {action}")
            print(f"{action_data['description']}\n")
            
            if 'options' in action_data:
                print(f"{colorize('Options:', 'cyan')}")
                for opt, desc in action_data['options'].items():
                    print(f"  {colorize(opt, 'yellow'):<20} {desc}")
                print()
            
            if 'examples' in action_data:
                print(f"{colorize('Examples:', 'cyan')}")
                for example in action_data['examples']:
                    print(f"  {colorize('$', 'green')} {example}")
                print()
        else:
            print(f"{colorize('Available actions:', 'cyan')}")
            for act in data.get('actions', {}).keys():
                print(f"  - {act}")
            print()
            
            if 'examples' in data:
                print(f"{colorize('Examples:', 'cyan')}")
                for example in data['examples']:
                    if example:
                        if example.startswith('#'):
                            print(f"  {colorize(example, 'yellow')}")
                        else:
                            print(f"  {colorize('$', 'green')} {example}")
                    else:
                        print()
```

### Fuzzy Command Matching & Did-You-Mean

Suggest corrections for typos and partial matches:

```python
# src/modules/cli/fuzzy.py
import difflib

def find_similar_commands(input_cmd, available_commands, cutoff=0.6):
    """Find similar commands using fuzzy matching."""
    matches = difflib.get_close_matches(
        input_cmd, 
        available_commands, 
        n=5, 
        cutoff=cutoff
    )
    return matches

def suggest_command(input_cmd, parser):
    """Suggest correct command when user makes a typo."""
    
    # Get all available commands
    all_commands = []
    
    # Top-level commands (domains)
    if hasattr(parser, '_subparsers'):
        for action in parser._subparsers._actions:
            if isinstance(action, argparse._SubParsersAction):
                all_commands.extend(action.choices.keys())
    
    # Find similar commands
    suggestions = find_similar_commands(input_cmd, all_commands)
    
    if suggestions:
        print(f"\n{colorize('Error:', 'red')} Unknown command '{input_cmd}'\n")
        print(f"{colorize('Did you mean:', 'yellow')}")
        for suggestion in suggestions:
            print(f"  {colorize('$', 'green')} flux {suggestion}")
        print()
        return True
    
    return False

def handle_command_error(error_msg, parser, args):
    """Handle command errors with helpful suggestions."""
    
    if 'invalid choice' in error_msg.lower():
        # Extract the invalid choice
        import re
        match = re.search(r"invalid choice: '(\w+)'", error_msg)
        if match:
            invalid_cmd = match.group(1)
            
            # Try to suggest corrections
            if suggest_command(invalid_cmd, parser):
                return
    
    # Check for common mistakes
    common_mistakes = {
        'start': 'play',
        'begin': 'play',
        'unpause': 'play',
        'halt': 'stop',
        'end': 'stop',
        'ls': 'list',
        'dir': 'list',
        'show': 'list',
        'rm': 'delete',
        'del': 'delete',
        'remove': 'delete',
    }
    
    if args and len(args) > 0:
        first_arg = args[0].lower()
        if first_arg in common_mistakes:
            print(f"\n{colorize('Hint:', 'yellow')} Try using '{common_mistakes[first_arg]}' instead of '{first_arg}'")
            print(f"  {colorize('$', 'green')} flux {' '.join([common_mistakes[first_arg]] + args[1:])}\n")
            return
    
    # Default error message
    print(f"\n{colorize('Error:', 'red')} {error_msg}")
    print(f"\nRun {colorize('flux --help', 'cyan')} for usage information.\n")
```

### Inline Command Hints

Show hints as users type incomplete commands:

```python
# src/modules/cli/hints.py

def show_incomplete_command_hint(parsed_args, parser):
    """Show hints for incomplete commands."""
    
    hints = {
        ('player',): "Available actions: play, pause, stop, status, next, prev, set",
        ('player', 'play'): "Options: -p/--player [video|artnet|all]",
        ('player', 'set'): "Available parameters: brightness, speed, fps, loop, hue",
        ('clip',): "Available actions: load, current, effects, layers, generator",
        ('clip', 'effect'): "Available actions: add, remove, set, toggle, clear",
        ('output',): "Available actions: list, add, enable, disable, remove, artnet",
        ('output', 'artnet'): "Available actions: settings, set, resolution, blackout, test, ips",
        ('playlist',): "Available actions: list, create, delete, rename, activate, view, show",
        ('effect',): "Available actions: list, add, set, remove, toggle, clear",
    }
    
    # Build command path from parsed args
    cmd_path = []
    if hasattr(parsed_args, 'domain') and parsed_args.domain:
        cmd_path.append(parsed_args.domain)
    if hasattr(parsed_args, 'action') and parsed_args.action:
        cmd_path.append(parsed_args.action)
    
    cmd_tuple = tuple(cmd_path)
    
    if cmd_tuple in hints:
        print(f"\n{colorize('Hint:', 'cyan')} {hints[cmd_tuple]}\n")
        return True
    
    return False

def show_available_subcommands(parser, domain=None):
    """Show available subcommands for a domain."""
    
    if not domain:
        # Show top-level domains
        print(f"\n{colorize('Available commands:', 'cyan')}")
        domains = [
            'player', 'clip', 'effect', 'layer', 'output', 
            'playlist', 'transition', 'session', 'config',
            'audio', 'sequence', 'content', 'project', 'plugin',
            'mapper', 'debug', 'log', 'perf', 'console'
        ]
        
        # Group by category
        categories = {
            'Playback': ['player', 'clip', 'effect', 'layer'],
            'Output': ['output', 'playlist', 'transition'],
            'Content': ['content', 'project', 'plugin'],
            'Audio': ['audio', 'sequence'],
            'System': ['session', 'config', 'debug', 'log', 'perf', 'console', 'mapper']
        }
        
        for category, commands in categories.items():
            print(f"\n  {colorize(category + ':', 'yellow')}")
            for cmd in commands:
                print(f"    {cmd}")
        
        print(f"\nRun {colorize('flux <command> --help', 'cyan')} for more information.\n")
```

### Command History

Implement persistent command history:

```python
# src/modules/cli/history.py
import os
import readline
import atexit

class CommandHistory:
    """Manage command history with persistence."""
    
    def __init__(self, history_file=None):
        if history_file is None:
            history_dir = os.path.expanduser('~/.flux')
            os.makedirs(history_dir, exist_ok=True)
            history_file = os.path.join(history_dir, 'history')
        
        self.history_file = history_file
        self.setup()
    
    def setup(self):
        """Setup readline and load history."""
        # Enable history
        readline.parse_and_bind('tab: complete')
        readline.parse_and_bind('set editing-mode emacs')
        
        # Load existing history
        if os.path.exists(self.history_file):
            readline.read_history_file(self.history_file)
        
        # Set history length
        readline.set_history_length(1000)
        
        # Save on exit
        atexit.register(self.save)
    
    def save(self):
        """Save history to file."""
        try:
            readline.write_history_file(self.history_file)
        except Exception as e:
            print(f"Warning: Could not save command history: {e}")
    
    def add(self, command):
        """Add command to history."""
        readline.add_history(command)
    
    def search(self, pattern):
        """Search history for pattern."""
        history = []
        for i in range(readline.get_current_history_length()):
            item = readline.get_history_item(i + 1)
            if item and pattern.lower() in item.lower():
                history.append(item)
        return history

# Usage in main CLI
def main():
    history = CommandHistory()
    
    # Interactive mode
    while True:
        try:
            cmd = input(colorize('flux> ', 'green'))
            if cmd.strip():
                history.add(cmd)
                execute_command(cmd)
        except KeyboardInterrupt:
            print("\nUse 'exit' to quit.")
        except EOFError:
            break
```

### Smart Error Messages

Provide actionable error messages with suggestions:

```python
# src/modules/cli/errors.py

class CLIError(Exception):
    """Base CLI error with helpful messaging."""
    
    def __init__(self, message, suggestion=None, examples=None):
        self.message = message
        self.suggestion = suggestion
        self.examples = examples or []
        super().__init__(message)
    
    def display(self):
        """Display formatted error message."""
        print(f"\n{colorize('Error:', 'red')} {self.message}\n")
        
        if self.suggestion:
            print(f"{colorize('Suggestion:', 'yellow')} {self.suggestion}\n")
        
        if self.examples:
            print(f"{colorize('Examples:', 'cyan')}")
            for example in self.examples:
                print(f"  {colorize('$', 'green')} {example}")
            print()

# Example error handlers
def handle_missing_player_error():
    raise CLIError(
        "No player specified",
        "Use -p/--player to specify which player to control",
        examples=[
            "flux player play -p video",
            "flux player play -p artnet",
            "flux player play --all"
        ]
    )

def handle_file_not_found_error(filename):
    raise CLIError(
        f"File not found: {filename}",
        "Check the file path or use tab completion to browse available files",
        examples=[
            f"flux content list  # List all available videos",
            f"flux clip load <TAB>  # Press TAB to see suggestions"
        ]
    )

def handle_api_connection_error():
    raise CLIError(
        "Could not connect to Flux API",
        "Make sure the Flux backend is running",
        examples=[
            "# Start the backend:",
            "python src/main.py",
            "",
            "# Check if it's running:",
            "curl http://localhost:5000/api/player/video/status"
        ]
    )
```

### Interactive Mode with Prompt

Provide an interactive REPL-style interface:

```python
# src/modules/cli/interactive.py

class InteractiveCLI:
    """Interactive mode with prompt and context."""
    
    def __init__(self, parser, api_client):
        self.parser = parser
        self.api_client = api_client
        self.history = CommandHistory()
        self.context = {}  # Store current context (player, clip, etc.)
    
    def run(self):
        """Run interactive CLI loop."""
        print(f"\n{colorize('Flux Interactive Mode', 'cyan')}")
        print(f"Type {colorize('help', 'yellow')} for available commands or {colorize('exit', 'yellow')} to quit.\n")
        
        while True:
            try:
                # Build prompt with context
                prompt = self.build_prompt()
                cmd = input(prompt)
                
                if not cmd.strip():
                    continue
                
                # Handle special commands
                if cmd.strip().lower() in ['exit', 'quit', 'q']:
                    print("Goodbye!")
                    break
                
                if cmd.strip().lower() == 'clear':
                    os.system('cls' if os.name == 'nt' else 'clear')
                    continue
                
                # Execute command
                self.history.add(cmd)
                self.execute(cmd)
                
            except KeyboardInterrupt:
                print(f"\n{colorize('Interrupted.', 'yellow')} Use 'exit' to quit.\n")
            except EOFError:
                print("\nGoodbye!")
                break
    
    def build_prompt(self):
        """Build context-aware prompt."""
        # Show current player in prompt
        player = self.context.get('player', 'none')
        prompt_parts = ['flux']
        
        if player != 'none':
            prompt_parts.append(f"({colorize(player, 'blue')})")
        
        prompt_parts.append('> ')
        return ' '.join(prompt_parts)
    
    def execute(self, cmd):
        """Execute command and update context."""
        try:
            # Parse command
            args = cmd.split()
            
            # Add default player if not specified and one is in context
            if 'player' in self.context and '-p' not in args:
                # Insert player flag for relevant commands
                if args and args[0] in ['clip', 'effect', 'layer']:
                    args.extend(['-p', self.context['player']])
            
            # Execute via parser
            parsed = self.parser.parse_args(args)
            result = execute_command(parsed)
            
            # Update context based on command
            if hasattr(parsed, 'player') and parsed.player:
                self.context['player'] = parsed.player
            
            # Display result
            if result:
                print(result)
        
        except Exception as e:
            if isinstance(e, CLIError):
                e.display()
            else:
                print(f"\n{colorize('Error:', 'red')} {str(e)}\n")
```

### Progress Indicators

Show progress for long-running operations:

```python
# src/modules/cli/progress.py
from tqdm import tqdm
import sys

def show_progress(iterable, description="Processing"):
    """Show progress bar for operations."""
    return tqdm(
        iterable,
        desc=colorize(description, 'cyan'),
        bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
        file=sys.stdout
    )

# Example usage
def batch_convert_videos(files):
    """Convert multiple videos with progress."""
    with show_progress(files, "Converting videos") as pbar:
        for file in pbar:
            pbar.set_postfix_str(f"Processing {os.path.basename(file)}")
            convert_video(file)
            pbar.update(1)

def wait_for_operation(operation_id, check_interval=0.5):
    """Wait for long operation with spinner."""
    import itertools
    import time
    
    spinner = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])
    
    while True:
        status = check_operation_status(operation_id)
        
        if status['complete']:
            print(f"\r{colorize('✓', 'green')} {status['message']}")
            break
        
        # Show spinner
        sys.stdout.write(f"\r{colorize(next(spinner), 'cyan')} {status['message']}")
        sys.stdout.flush()
        time.sleep(check_interval)
```

### Colorized Output

Consistent and accessible color scheme:

```python
# src/modules/cli/colors.py

class Colors:
    """ANSI color codes."""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'

def colorize(text, color='white', bold=False):
    """Apply color to text."""
    # Check if colors are disabled
    if os.getenv('NO_COLOR') or not sys.stdout.isatty():
        return text
    
    color_code = getattr(Colors, color.upper(), Colors.WHITE)
    bold_code = Colors.BOLD if bold else ''
    
    return f"{bold_code}{color_code}{text}{Colors.RESET}"

def print_table(headers, rows, colors=None):
    """Print formatted table with colors."""
    from tabulate import tabulate
    
    # Apply colors to headers
    if colors:
        colored_headers = [colorize(h, colors.get('header', 'cyan'), bold=True) for h in headers]
    else:
        colored_headers = headers
    
    # Print table
    print(tabulate(rows, headers=colored_headers, tablefmt='simple'))

def print_status(status, message):
    """Print status message with icon."""
    icons = {
        'success': colorize('✓', 'green'),
        'error': colorize('✗', 'red'),
        'warning': colorize('⚠', 'yellow'),
        'info': colorize('ℹ', 'blue'),
    }
    
    icon = icons.get(status, '•')
    print(f"{icon} {message}")
```

### Usage Examples

**Tab Completion in Action:**
```bash
$ flux pla<TAB>
player  playlist

$ flux player <TAB>
play  pause  stop  clear  status  next  prev  set  master  sync  settings

$ flux player set <TAB>
brightness  speed  fps  loop  hue

$ flux clip load <TAB>
video1.mp4  video2.mp4  subfolder/  test.mov
```

**Fuzzy Matching:**
```bash
$ flux playr play
Error: Unknown command 'playr'

Did you mean:
  $ flux player

$ flux plya
Error: Unknown command 'plya'

Did you mean:
  $ flux play
  $ flux player
```

**Interactive Mode:**
```bash
$ flux --interactive

Flux Interactive Mode
Type help for available commands or exit to quit.

flux> player play -p video
✓ Video player started

flux (video)> clip load test.mp4
✓ Loaded clip test.mp4 (id: abc123)

flux (video)> effect add blur
✓ Added blur effect

flux (video)> effect set 0 radius 10
✓ Updated effect parameter: radius=10

flux (video)> exit
Goodbye!
```

**Smart Errors:**
```bash
$ flux clip load nonexistent.mp4
Error: File not found: nonexistent.mp4

Suggestion: Check the file path or use tab completion to browse available files

Examples:
  $ flux content list  # List all available videos
  $ flux clip load <TAB>  # Press TAB to see suggestions
```

---

## MAINTAINING API-CLI CONSISTENCY

As the project evolves, new API endpoints will be added. This section provides tools and strategies to ensure every API endpoint has a corresponding CLI implementation.

### API Discovery Script

Create a script that scans all API endpoints and validates they have CLI mappings:

**File: `tools/sync_cli_api.py`**

```python
#!/usr/bin/env python3
"""
API-CLI Sync Tool

Scans all API route files to discover endpoints and checks if they have
corresponding CLI commands documented in CLI_REDESIGN.md.

Usage:
    python tools/sync_cli_api.py --check              # Check for missing mappings
    python tools/sync_cli_api.py --report             # Generate detailed report
    python tools/sync_cli_api.py --generate-stubs     # Generate CLI command stubs
"""

import os
import re
import glob
import json
import argparse
from pathlib import Path
from collections import defaultdict


class APIEndpoint:
    """Represents an API endpoint."""
    
    def __init__(self, path, methods, handler, file_path, line_number):
        self.path = path
        self.methods = methods
        self.handler = handler
        self.file_path = file_path
        self.line_number = line_number
        self.cli_command = None
        self.cli_mapped = False
    
    def __repr__(self):
        return f"<APIEndpoint {self.methods} {self.path}>"
    
    def to_dict(self):
        return {
            'path': self.path,
            'methods': self.methods,
            'handler': self.handler,
            'file': self.file_path,
            'line': self.line_number,
            'cli_command': self.cli_command,
            'cli_mapped': self.cli_mapped
        }


class APIDiscovery:
    """Discover all API endpoints in the project."""
    
    def __init__(self, api_root='src/modules/api'):
        self.api_root = api_root
        self.endpoints = []
    
    def discover(self):
        """Scan all Python files in API directory for route decorators."""
        pattern = os.path.join(self.api_root, '**', '*.py')
        files = glob.glob(pattern, recursive=True)
        
        for file_path in files:
            self._scan_file(file_path)
        
        return self.endpoints
    
    def _scan_file(self, file_path):
        """Scan a single file for API routes."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return
        
        # Pattern for Flask route decorators
        # Matches: @app.route('/api/path', methods=['POST', 'GET'])
        #          @bp.route('/api/path', methods=['POST'])
        route_pattern = re.compile(
            r"@\w+\.route\s*\(\s*['\"](/api/[^'\"]+)['\"](?:.*?methods\s*=\s*\[([^\]]+)\])?"
        )
        
        for i, line in enumerate(lines, 1):
            match = route_pattern.search(line)
            if match:
                path = match.group(1)
                methods_str = match.group(2) if match.group(2) else 'GET'
                
                # Extract method names
                methods = re.findall(r"['\"](\w+)['\"]", methods_str)
                if not methods:
                    methods = ['GET']
                
                # Get handler function name (next def line)
                handler = None
                for j in range(i, min(i + 5, len(lines))):
                    func_match = re.search(r'def\s+(\w+)\s*\(', lines[j])
                    if func_match:
                        handler = func_match.group(1)
                        break
                
                # Only include endpoints that modify state (POST/PUT/PATCH/DELETE)
                # or are significant GET endpoints
                if any(m in ['POST', 'PUT', 'PATCH', 'DELETE'] for m in methods):
                    endpoint = APIEndpoint(
                        path=path,
                        methods=methods,
                        handler=handler,
                        file_path=file_path,
                        line_number=i
                    )
                    self.endpoints.append(endpoint)
    
    def categorize_endpoints(self):
        """Group endpoints by domain."""
        categories = defaultdict(list)
        
        for endpoint in self.endpoints:
            # Extract domain from path (e.g., /api/player/... -> player)
            parts = endpoint.path.split('/')
            if len(parts) >= 3:
                domain = parts[2]  # /api/DOMAIN/...
                categories[domain].append(endpoint)
            else:
                categories['other'].append(endpoint)
        
        return dict(categories)


class CLIDocParser:
    """Parse CLI_REDESIGN.md to find documented CLI commands."""
    
    def __init__(self, doc_path='docs/CLI_REDESIGN.md'):
        self.doc_path = doc_path
        self.api_cli_mappings = {}
    
    def parse(self):
        """Parse the documentation and extract API-CLI mappings."""
        try:
            with open(self.doc_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"Error: Could not read {self.doc_path}: {e}")
            return {}
        
        # Pattern to match mapping tables:
        # | API Endpoint | CLI Command | Example |
        # | POST /api/player/<id>/play | player play | player play -p video |
        
        # Match table rows with API paths
        pattern = re.compile(
            r'\|\s*(?:GET|POST|PUT|PATCH|DELETE)\s+(/api/[^\s|]+)\s*\|\s*`([^`]+)`',
            re.MULTILINE
        )
        
        for match in pattern.finditer(content):
            api_path = match.group(1)
            cli_command = match.group(2).strip()
            
            # Normalize path (replace <param> with actual placeholders)
            normalized_path = re.sub(r'<[^>]+>', '*', api_path)
            
            self.api_cli_mappings[api_path] = cli_command
        
        return self.api_cli_mappings
    
    def find_cli_command(self, api_path):
        """Find CLI command for an API path."""
        # Try exact match first
        if api_path in self.api_cli_mappings:
            return self.api_cli_mappings[api_path]
        
        # Try pattern matching (for parameterized paths)
        api_pattern = re.sub(r'<[^>]+>', '[^/]+', api_path)
        for doc_path, cli_cmd in self.api_cli_mappings.items():
            doc_pattern = re.sub(r'<[^>]+>', '[^/]+', doc_path)
            if re.match(doc_pattern, api_path):
                return cli_cmd
        
        return None


class APICliSyncChecker:
    """Check consistency between API endpoints and CLI commands."""
    
    def __init__(self, api_root='src/modules/api', doc_path='docs/CLI_REDESIGN.md'):
        self.discovery = APIDiscovery(api_root)
        self.doc_parser = CLIDocParser(doc_path)
        self.endpoints = []
        self.mappings = {}
    
    def check(self):
        """Run consistency check."""
        print("🔍 Discovering API endpoints...")
        self.endpoints = self.discovery.discover()
        print(f"   Found {len(self.endpoints)} endpoints\n")
        
        print("📖 Parsing CLI documentation...")
        self.mappings = self.doc_parser.parse()
        print(f"   Found {len(self.mappings)} CLI mappings\n")
        
        print("🔄 Checking API-CLI consistency...")
        
        # Check each endpoint for CLI mapping
        missing = []
        for endpoint in self.endpoints:
            cli_cmd = self.doc_parser.find_cli_command(endpoint.path)
            if cli_cmd:
                endpoint.cli_command = cli_cmd
                endpoint.cli_mapped = True
            else:
                missing.append(endpoint)
        
        return missing
    
    def report(self, missing):
        """Generate report of missing CLI mappings."""
        if not missing:
            print("✅ All API endpoints have CLI mappings!\n")
            return
        
        print(f"❌ Found {len(missing)} API endpoints without CLI mappings:\n")
        
        # Group by category
        categorized = defaultdict(list)
        for endpoint in missing:
            parts = endpoint.path.split('/')
            domain = parts[2] if len(parts) >= 3 else 'other'
            categorized[domain].append(endpoint)
        
        for domain, endpoints in sorted(categorized.items()):
            print(f"\n📦 {domain.upper()} ({len(endpoints)} missing)")
            print("=" * 80)
            for ep in endpoints:
                methods_str = ', '.join(ep.methods)
                print(f"\n  Path:    {ep.path}")
                print(f"  Methods: {methods_str}")
                print(f"  Handler: {ep.handler}")
                print(f"  File:    {ep.file_path}:{ep.line_number}")
                print(f"  Suggest: {self._suggest_cli_command(ep)}")
    
    def _suggest_cli_command(self, endpoint):
        """Suggest a CLI command for an endpoint."""
        path = endpoint.path
        method = endpoint.methods[0] if endpoint.methods else 'GET'
        
        # Parse path to suggest command
        parts = [p for p in path.split('/') if p and p != 'api']
        
        if len(parts) >= 2:
            domain = parts[0]
            action = parts[-1] if parts[-1] not in ['<player_id>', '<clip_id>'] else parts[-2]
            
            # Map HTTP methods to actions
            if method == 'POST':
                if 'add' in action:
                    action = 'add'
                elif 'create' in action:
                    action = 'create'
                elif action in ['enable', 'disable', 'toggle', 'start', 'stop']:
                    pass  # Keep as is
                else:
                    action = 'set'
            elif method == 'DELETE':
                action = 'remove' if 'remove' in action else 'delete'
            elif method == 'PUT' or method == 'PATCH':
                action = 'update'
            
            return f"{domain} {action} [options]"
        
        return "NEEDS MANUAL MAPPING"
    
    def generate_stubs(self, missing):
        """Generate CLI command stub code for missing endpoints."""
        if not missing:
            print("✅ No stubs needed - all endpoints mapped!\n")
            return
        
        print("📝 Generating CLI command stubs...\n")
        
        categorized = defaultdict(list)
        for endpoint in missing:
            parts = endpoint.path.split('/')
            domain = parts[2] if len(parts) >= 3 else 'other'
            categorized[domain].append(endpoint)
        
        for domain, endpoints in sorted(categorized.items()):
            print(f"\n# {domain.upper()} Commands")
            print("=" * 80)
            print(f"# File: src/modules/cli/commands/{domain}.py\n")
            
            for ep in endpoints:
                func_name = ep.handler or 'unknown'
                suggested_cmd = self._suggest_cli_command(ep)
                
                print(f"def cli_{func_name}(args):")
                print(f'    """')
                print(f'    {" ".join(ep.methods)} {ep.path}')
                print(f'    CLI: {suggested_cmd}')
                print(f'    """')
                print(f'    # TODO: Implement CLI command')
                print(f'    # API endpoint: {ep.file_path}:{ep.line_number}')
                print(f'    pass\n')
    
    def export_json(self, output_file='api_cli_report.json'):
        """Export report as JSON."""
        data = {
            'total_endpoints': len(self.endpoints),
            'mapped_endpoints': sum(1 for ep in self.endpoints if ep.cli_mapped),
            'missing_endpoints': sum(1 for ep in self.endpoints if not ep.cli_mapped),
            'endpoints': [ep.to_dict() for ep in self.endpoints]
        }
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n📊 Report exported to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Check API-CLI consistency and generate reports'
    )
    parser.add_argument(
        '--check', 
        action='store_true',
        help='Check for missing CLI mappings'
    )
    parser.add_argument(
        '--report', 
        action='store_true',
        help='Generate detailed report'
    )
    parser.add_argument(
        '--generate-stubs', 
        action='store_true',
        help='Generate CLI command stubs for missing mappings'
    )
    parser.add_argument(
        '--export-json',
        metavar='FILE',
        help='Export report as JSON'
    )
    parser.add_argument(
        '--api-root',
        default='src/modules/api',
        help='Root directory for API modules (default: src/modules/api)'
    )
    parser.add_argument(
        '--doc-path',
        default='docs/CLI_REDESIGN.md',
        help='Path to CLI redesign documentation (default: docs/CLI_REDESIGN.md)'
    )
    
    args = parser.parse_args()
    
    # If no flags, show help
    if not any([args.check, args.report, args.generate_stubs, args.export_json]):
        parser.print_help()
        return
    
    # Create checker
    checker = APICliSyncChecker(args.api_root, args.doc_path)
    
    # Run check
    missing = checker.check()
    
    # Generate outputs
    if args.check or args.report:
        checker.report(missing)
    
    if args.generate_stubs:
        checker.generate_stubs(missing)
    
    if args.export_json:
        checker.export_json(args.export_json)
    
    # Exit with error code if missing mappings
    if args.check and missing:
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
```

### Usage Examples

**Check for missing CLI mappings:**
```bash
python tools/sync_cli_api.py --check
```

Output:
```
🔍 Discovering API endpoints...
   Found 156 endpoints

📖 Parsing CLI documentation...
   Found 142 CLI mappings

🔄 Checking API-CLI consistency...

❌ Found 14 API endpoints without CLI mappings:

📦 PLAYER (3 missing)
================================================================================

  Path:    /api/player/<player_id>/volume
  Methods: POST
  Handler: set_volume
  File:    src/modules/api/player/playback.py:2547
  Suggest: player set [options]

  ...
```

**Generate detailed report:**
```bash
python tools/sync_cli_api.py --report
```

**Generate CLI command stubs:**
```bash
python tools/sync_cli_api.py --generate-stubs > stubs.py
```

Output:
```python
# PLAYER Commands
================================================================================
# File: src/modules/cli/commands/player.py

def cli_set_volume(args):
    """
    POST /api/player/<player_id>/volume
    CLI: player set [options]
    """
    # TODO: Implement CLI command
    # API endpoint: src/modules/api/player/playback.py:2547
    pass
```

**Export as JSON for CI/CD:**
```bash
python tools/sync_cli_api.py --check --export-json report.json
```

### Integration with Development Workflow

#### 1. Run During Development

Add to your development routine:

```bash
# Before committing
python tools/sync_cli_api.py --check

# If new endpoints found
python tools/sync_cli_api.py --report
python tools/sync_cli_api.py --generate-stubs >> src/modules/cli/commands/new.py
```

#### 2. Pre-commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash

echo "🔍 Checking API-CLI consistency..."

python tools/sync_cli_api.py --check

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ New API endpoints detected without CLI mappings!"
    echo ""
    echo "Please:"
    echo "  1. Update docs/CLI_REDESIGN.md with CLI commands"
    echo "  2. Implement CLI commands in src/modules/cli/commands/"
    echo ""
    echo "Or run: python tools/sync_cli_api.py --report"
    echo ""
    exit 1
fi

echo "✅ API-CLI consistency check passed"
exit 0
```

Make it executable:
```bash
chmod +x .git/hooks/pre-commit
```

#### 3. CI/CD Integration

Add to GitHub Actions (`.github/workflows/cli-sync.yml`):

```yaml
name: CLI-API Sync Check

on:
  pull_request:
    paths:
      - 'src/modules/api/**/*.py'
      - 'docs/CLI_REDESIGN.md'

jobs:
  check-sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Check API-CLI consistency
        run: |
          python tools/sync_cli_api.py --check --export-json report.json
          
          if [ $? -ne 0 ]; then
            echo "::error::New API endpoints without CLI mappings detected"
            python tools/sync_cli_api.py --report
            exit 1
          fi
      
      - name: Upload report
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: api-cli-report
          path: report.json
```

### Developer Checklist

When adding new API endpoints, follow this checklist:

- [ ] **API Implementation**
  - [ ] Created API endpoint in `src/modules/api/`
  - [ ] Added docstring with description
  - [ ] Added request/response validation

- [ ] **CLI Documentation**
  - [ ] Added entry to `docs/CLI_REDESIGN.md`
  - [ ] Included API endpoint → CLI command mapping
  - [ ] Added usage examples

- [ ] **CLI Implementation**
  - [ ] Implemented CLI command in `src/modules/cli/commands/`
  - [ ] Added argument parser
  - [ ] Added help text
  - [ ] Added tab completion
  - [ ] Added error handling

- [ ] **Testing**
  - [ ] Tested API endpoint manually
  - [ ] Tested CLI command manually
  - [ ] Added unit tests
  - [ ] Ran `python tools/sync_cli_api.py --check`

- [ ] **Documentation**
  - [ ] Updated CHANGELOG.md
  - [ ] Updated API.md (if needed)

### Maintenance

Run the sync check regularly:

```bash
# Weekly check
python tools/sync_cli_api.py --report --export-json weekly_report.json

# Before releases
python tools/sync_cli_api.py --check || exit 1
```

Track coverage over time:
```bash
# Extract stats from JSON report
jq '.mapped_endpoints, .total_endpoints' report.json
```

### Benefits

✅ **Automatic Discovery**: No need to manually track endpoints  
✅ **Consistency**: Ensures every API has a CLI command  
✅ **Documentation**: Generates stubs and reports  
✅ **CI/CD Ready**: Integrates with automated workflows  
✅ **Developer Friendly**: Clear guidance on what needs implementation  

---

## MIGRATION PLAN

1. **Phase 1**: Implement core commands (player, clip, effect)
2. **Phase 2**: Implement playlist and output commands
3. **Phase 3**: Implement session and config commands
4. **Phase 4**: Implement advanced features (audio, sequences, mapper)
5. **Phase 5**: Deprecate old CLI commands
6. **Phase 6**: Remove legacy code

---

## EXAMPLES

### Common Workflows

**Load and play a video:**
```bash
clip load video.mp4 -p video
player play -p video
```

**Add effects to current clip:**
```bash
clip effect add $(clip current --json | jq -r .clip_id) blur
clip effect set $(clip current --json | jq -r .clip_id) 0 radius 10
```

**Create and activate playlist:**
```bash
playlist create "My Show"
playlist activate $(playlist list --json | jq -r '.[0].id')
```

**Configure Art-Net output:**
```bash
output artnet set --ip 192.168.1.11 --universe 0
output artnet resolution 100 100
output artnet test
```

**Audio sequencer workflow:**
```bash
audio sequencer upload track.mp3
audio sequencer load track.mp3
audio sequencer split add 10.0
audio sequencer split add 20.0
audio sequencer slot 0 5
audio sequencer mode on
audio sequencer play
```

---

## CHANGELOG

- **2026-03-03**: Initial CLI redesign documentation
- **2026-03-03**: Added comprehensive CLI User Experience section with tab completion, fuzzy matching, interactive help, command history, and smart error handling
- **2026-03-03**: Added API-CLI consistency tools with automatic discovery script (`tools/sync_cli_api.py`), pre-commit hooks, CI/CD integration, and developer checklist
