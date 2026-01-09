# Sequence Architecture Refactor

## Problem Statement

Current architecture stores sequences globally, separate from their effects. This causes:
1. **Clip cycling breaks sequences** - New clip IDs generate new UIDs, sequences don't match
2. **No proper ownership** - Sequences aren't tied to their effects
3. **Session restore fails** - Can't properly restore effect+sequence state
4. **No layer support** - Sequences can't target layer-specific effects

## Desired Architecture

### Hierarchy
```
Playlist (unique name)
└── Clip (UUID)
    ├── Effect (UUID) - clip-level effect
    │   ├── plugin_id: "transform"
    │   ├── instance_id: 12345
    │   ├── parameters: {...}
    │   └── sequences: {
    │         "scale_xy": {
    │           "sequence_id": "seq_xxx",
    │           "type": "timeline",
    │           "config": {...},
    │           "enabled": true
    │         }
    │       }
    └── Layers []
        └── Layer (UUID)
            └── Effect (UUID) - layer-specific effect
                ├── plugin_id: "blur"
                ├── instance_id: 67890
                ├── parameters: {...}
                └── sequences: {
                      "amount": {...}
                    }
```

### Storage Structure

**clip_registry.clips[clip_uuid]:**
```python
{
  'clip_id': 'uuid',
  'effects': [
    {
      'plugin_id': 'transform',
      'instance_id': 12345,
      'parameters': {'scale_xy': 100, ...},
      'sequences': {
        'scale_xy': {
          'sequence_id': 'seq_xxx',
          'type': 'timeline',
          'enabled': true,
          'config': {
            'duration': 5,
            'min_value': 50,
            'max_value': 200,
            'loop_mode': 'loop',
            ...
          }
        }
      }
    }
  ],
  'layers': [
    {
      'layer_id': 'layer_uuid',
      'effects': [
        {
          'plugin_id': 'blur',
          'sequences': {'amount': {...}}
        }
      ]
    }
  ]
}
```

## Implementation Plan

### Phase 1: Update Data Structures

**1.1 ClipRegistry - Add sequence storage to effects**
- Modify `add_effect_to_clip()` to initialize `sequences: {}`
- Add `add_sequence_to_effect(clip_id, effect_index, param_name, sequence_config)`
- Add `remove_sequence_from_effect(clip_id, effect_index, param_name)`
- Add `get_effect_sequences(clip_id, effect_index)`
- Update layer effects to also support sequences

**1.2 SequenceManager - Load sequences from active clips**
- Keep global `self.sequences` for active sequences only
- Add `load_sequences_from_clip(clip_id)` - extracts all sequences from clip effects
- Add `unload_sequences_for_clip(clip_id)` - removes sequences when clip becomes inactive
- Modify `update_all()` to work with loaded sequences
- Keep sequence creation/update/delete APIs but persist to clip_registry

### Phase 2: API Changes

**2.1 Sequence Creation API (api_sequences.py)**
- Extract `clip_id` and `effect_index` from UID
- Create sequence object as before
- Store in `clip_registry.clips[clip_id]['effects'][effect_index]['sequences'][param_name]`
- Load into `sequence_manager` for immediate activation
- Remove old global storage

**2.2 Sequence Update/Delete APIs**
- Look up sequence in clip_registry by traversing effects
- Update both clip_registry (persistent) and sequence_manager (active)
- On delete: remove from both places

### Phase 3: Player Integration

**3.1 Clip Loading (player_core.py / layer_manager.py)**
- When loading clip layers: `sequence_manager.load_sequences_from_clip(clip_id)`
- When unloading clip: `sequence_manager.unload_sequences_for_clip(clip_id)`
- This ensures only active clip sequences are running

**3.2 Effect Instance Tracking**
- Store effect `instance_id` in clip_registry
- Match running effect instances to their sequences via instance_id
- Sequences find their target via: clip_id → effect_index → instance_id → parameter

### Phase 4: Session State

**4.1 Save**
- Iterate through all clips in clip_registry
- For each effect, serialize its sequences into effect data
- Save entire clip tree (clips → effects → sequences)
- Remove old flat sequence storage

**4.2 Restore**
- Load clips with their effects and sequences
- When player loads a clip, sequences are auto-loaded via `load_sequences_from_clip()`
- No separate sequence restoration needed

### Phase 5: UID System Update

**Current:** `param_clip_{clip_id}_{param_name}_{uuid_short}`
- Problem: Multiple effects on same clip have same UID pattern

**New:** `param_clip_{clip_id}_effect_{effect_index}_{param_name}`
- Uniquely identifies which effect the parameter belongs to
- For layers: `param_clip_{clip_id}_layer_{layer_idx}_effect_{effect_idx}_{param_name}`
- No need for uuid_short suffix since effect_index is unique per clip

## Migration Strategy

1. **Backward Compatibility**
   - Detect old-style session states with flat sequence storage
   - Attempt to match sequences to effects by UID parsing
   - Log warnings for sequences that can't be migrated
   
2. **Gradual Rollout**
   - Phase 1-2: New sequences use new architecture
   - Old sequences continue to work (dual-mode)
   - Phase 3-5: Full cutover, remove old code

3. **Testing**
   - Create clip with effects
   - Add sequences to multiple effects
   - Cycle through playlist
   - Verify sequences persist and re-apply correctly
   - Test save/load session state

## Benefits

✅ **Proper ownership** - Sequences belong to effects
✅ **Clip cycling works** - Sequences move with clip
✅ **Layer support** - Sequences on layer effects
✅ **Clean session state** - Tree structure mirrors runtime
✅ **Easier debugging** - Clear hierarchy
✅ **Future-proof** - Supports effect presets, copy/paste effects with sequences

## Files to Modify

1. `src/modules/clip_registry.py` - Add sequence storage to effects
2. `src/modules/sequences/sequence_manager.py` - Load from clips, not global
3. `src/modules/api_sequences.py` - Store in clip_registry
4. `src/modules/session_state.py` - Save/load tree structure
5. `src/modules/player_core.py` - Load/unload sequences with clips
6. `src/modules/player/layer_manager.py` - Load/unload sequences with layers
7. `src/modules/uid_registry.py` - Update UID format if needed

## Estimated Effort

- Phase 1 (Data Structures): 2-3 hours
- Phase 2 (API Changes): 2-3 hours  
- Phase 3 (Player Integration): 2-3 hours
- Phase 4 (Session State): 1-2 hours
- Phase 5 (UID System): 1-2 hours
- Testing & Bug Fixes: 2-3 hours

**Total: 10-16 hours**
