"""
Sequencer Integration — audio-driven master timeline control.

All public functions take ``mgr`` (PlayerManager instance) as first argument
so they can be called as standalone functions or as thin method delegates.

Entry points (called from PlayerManager):
    init_sequencer(mgr)
    set_sequencer_mode(mgr, enabled)
    sequencer_advance_slaves(mgr, slot_index, force_reload=False)
    update_all_slave_caches(mgr)
    update_sequences(mgr, dt)

Internal callbacks (wired by init_sequencer):
    _on_slot_change(mgr, slot_index)
    _on_position_update(mgr, position, slot_index)
"""
from __future__ import annotations
import time
import numpy as np
import cv2
from ..core.logger import get_logger

logger = get_logger(__name__)


# ─── Lifecycle ────────────────────────────────────────────────────────────────

def init_sequencer(mgr) -> None:
    """Instantiate AudioSequencer and wire its callbacks onto *mgr*."""
    try:
        from ..audio.sequencer import AudioSequencer
        mgr.sequencer = AudioSequencer(player_manager=mgr)

        # Bind callbacks as closures so they carry mgr without coupling
        # AudioSequencer to PlayerManager.
        mgr.sequencer.on_slot_change = lambda slot_index: _on_slot_change(mgr, slot_index)
        mgr.sequencer.on_position_update = lambda pos, slot: _on_position_update(mgr, pos, slot)

        logger.debug("🎵 AudioSequencer initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize sequencer: {e}", exc_info=True)


# ─── Mode control ─────────────────────────────────────────────────────────────

def set_sequencer_mode(mgr, enabled: bool) -> None:
    """Enable / disable sequencer mode.

    When enabled, the sequencer becomes the MASTER timeline controller and all
    playlists become slaves following slot boundaries.  Normal Master/Slave via
    Transport is disabled while sequencer mode is active.
    """
    mgr.sequencer_mode_active = enabled

    # Refresh slave-detection cache in every player.
    update_all_slave_caches(mgr)

    if enabled:
        old_master = mgr.master_playlist
        mgr.master_playlist = None
        logger.debug(
            f"🎵 SEQUENCER MODE ON: sequencer is MASTER, all playlists are SLAVES "
            f"(previous master: {old_master})"
        )
    else:
        logger.debug("🎵 SEQUENCER MODE OFF: normal master/slave operation")

    if mgr.socketio:
        try:
            mgr.socketio.emit(
                'sequencer_mode_changed',
                {'enabled': enabled, 'master_playlist': mgr.master_playlist},
                namespace='/player',
            )
        except Exception as e:
            logger.error(f"❌ Error emitting sequencer_mode_changed: {e}")


# ─── Slot advance ─────────────────────────────────────────────────────────────

def sequencer_advance_slaves(mgr, slot_index: int, force_reload: bool = False) -> None:
    """Advance every player to the clip that matches *slot_index*.

    Called when the sequencer crosses a slot boundary.  Slot index maps
    directly to clip index (slot 0 → clip 0, slot 1 → clip 1, …).
    """
    logger.debug(f"🎯 Sequencer slot {slot_index}: loading clip index in all playlists")

    if not mgr.sequencer_mode_active:
        logger.warning("⚠️ Sequencer mode not active, skipping slave advance")
        return

    for player_id, player in mgr.players.items():
        if not player or not player.playlist_manager.playlist:
            continue

        playlist_length = len(player.playlist_manager.playlist)

        # Slot beyond playlist length → stop + black screen
        if slot_index >= playlist_length:
            player.stop()
            black_rgb = np.zeros((player.canvas_height, player.canvas_width, 3), dtype=np.uint8)

            if hasattr(player, 'routing_bridge') and player.routing_bridge and player.enable_artnet:
                try:
                    player.routing_bridge.process_frame(black_rgb)
                except Exception as e:
                    logger.error(f"Failed to send black frame via routing_bridge: {e}")

            player.last_video_frame = cv2.cvtColor(black_rgb, cv2.COLOR_RGB2BGR)
            player.last_frame = None
            logger.debug(
                f"⏹️ Sequencer slot {slot_index}: {player_id} stopped "
                f"(only has {playlist_length} clips) - black screen"
            )
            continue

        current_index = getattr(player, 'current_clip_index', -1)
        target_index = slot_index

        if target_index != current_index or force_reload:
            logger.debug(f"🔄 Sequencer: loading {player_id} clip {target_index}")
            success = player.load_clip_by_index(target_index, notify_manager=False)
            if not success:
                logger.warning(f"❌ Failed to load {player_id} clip {target_index}")
                continue
            if not player.is_playing:
                player.start()

        # Always emit playlist.changed so the frontend stays in sync.
        if mgr.socketio:
            mgr.socketio.emit(
                'playlist.changed',
                {'player_id': player_id, 'current_index': target_index},
                namespace='/player',
            )

    if mgr.socketio:
        try:
            mgr.socketio.emit(
                'sequencer_slot_advance',
                {'slot_index': slot_index, 'timestamp': time.time()},
                namespace='/player',
            )
        except Exception as e:
            logger.error(f"❌ Error emitting sequencer_slot_advance: {e}")


# ─── Slave cache ──────────────────────────────────────────────────────────────

def update_all_slave_caches(mgr) -> None:
    """Refresh ``_is_slave_cached`` on every player after state changes."""
    for player_id, player in mgr.players.items():
        if player:
            is_slave = mgr.sequencer_mode_active or (
                mgr.master_playlist is not None and not mgr.is_master(player_id)
            )
            player._is_slave_cached = is_slave
            logger.debug(f"Updated slave cache for {player_id}: {is_slave}")
        else:
            logger.debug(f"Skipping slave cache update for {player_id}: player is None")


# ─── Sequence parameter update ────────────────────────────────────────────────

def update_sequences(mgr, dt: float) -> None:
    """Tick all dynamic parameter sequences (call from render loop).

    Args:
        dt: Elapsed time in seconds since last update.
    """
    if hasattr(mgr, 'sequence_manager') and mgr.sequence_manager:
        try:
            mgr.sequence_manager.update_all(dt, mgr)
        except Exception as e:
            logger.error(f"Error updating sequences: {e}", exc_info=True)


# ─── Internal callbacks ───────────────────────────────────────────────────────

def _on_slot_change(mgr, slot_index: int) -> None:
    """Invoked by AudioSequencer when a new slot boundary is crossed."""
    logger.debug(f"🎵 Sequencer slot change callback: slot {slot_index}")


def _on_position_update(mgr, position: float, slot_index: int) -> None:
    """Invoked by AudioSequencer ~10×/s; throttled to ≤5 WebSocket pushes/s."""
    if not hasattr(mgr, '_last_position_update'):
        mgr._last_position_update = 0.0

    now = time.time()
    if now - mgr._last_position_update < 0.2:   # 200 ms throttle → 5/s
        return
    mgr._last_position_update = now

    if mgr.socketio:
        try:
            mgr.socketio.emit(
                'sequencer_position',
                {'position': position, 'slot_index': slot_index},
                namespace='/player',
            )
        except Exception:
            pass   # don't spam logs on transient WebSocket errors
