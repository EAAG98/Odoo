# Part of Odoo. See LICENSE file for full copyright and licensing details.

import gc
from datetime import timedelta
from freezegun import freeze_time

from odoo.tests import common
from .common import WebsocketCase
from ..websocket import (
    CloseCode,
    Frame,
    Opcode,
    TimeoutManager,
    TimeoutReason,
    Websocket
)


@common.tagged('post_install', '-at_install')
class TestWebsocketCaryall(WebsocketCase):
    def test_instances_weak_set(self):
        gc.collect()
        first_ws = self.websocket_connect()
        second_ws = self.websocket_connect()
        self.assertEqual(len(Websocket._instances), 2)
        first_ws.close(CloseCode.CLEAN)
        second_ws.close(CloseCode.CLEAN)
        self.wait_remaining_websocket_connections()
        # serve_forever_patch prevent websocket instances from being
        # collected. Stop it now.
        self._serve_forever_patch.stop()
        gc.collect()
        self.assertEqual(len(Websocket._instances), 0)

    def test_timeout_manager_no_response_timeout(self):
        with freeze_time('2022-08-19') as frozen_time:
            timeout_manager = TimeoutManager()
            # A PING frame was just sent, if no pong has been received
            # within TIMEOUT seconds, the connection should have timed out.
            timeout_manager.acknowledge_frame_sent(Frame(Opcode.PING))
            self.assertEqual(timeout_manager._awaited_opcode, Opcode.PONG)
            frozen_time.tick(delta=timedelta(seconds=TimeoutManager.TIMEOUT / 2))
            self.assertFalse(timeout_manager.has_timed_out())
            frozen_time.tick(delta=timedelta(seconds=TimeoutManager.TIMEOUT / 2))
            self.assertTrue(timeout_manager.has_timed_out())
            self.assertEqual(timeout_manager.timeout_reason, TimeoutReason.NO_RESPONSE)

            timeout_manager = TimeoutManager()
            # A CLOSE frame was just sent, if no close has been received
            # within TIMEOUT seconds, the connection should have timed out.
            timeout_manager.acknowledge_frame_sent(Frame(Opcode.CLOSE))
            self.assertEqual(timeout_manager._awaited_opcode, Opcode.CLOSE)
            frozen_time.tick(delta=timedelta(seconds=TimeoutManager.TIMEOUT / 2))
            self.assertFalse(timeout_manager.has_timed_out())
            frozen_time.tick(delta=timedelta(seconds=TimeoutManager.TIMEOUT / 2))
            self.assertTrue(timeout_manager.has_timed_out())
            self.assertEqual(timeout_manager.timeout_reason, TimeoutReason.NO_RESPONSE)

    def test_timeout_manager_keep_alive_timeout(self):
        with freeze_time('2022-08-19') as frozen_time:
            timeout_manager = TimeoutManager()
            frozen_time.tick(delta=timedelta(seconds=TimeoutManager.KEEP_ALIVE_TIMEOUT / 2))
            self.assertFalse(timeout_manager.has_timed_out())
            frozen_time.tick(delta=timedelta(seconds=TimeoutManager.KEEP_ALIVE_TIMEOUT / 2))
            self.assertTrue(timeout_manager.has_timed_out())
            self.assertEqual(timeout_manager.timeout_reason, TimeoutReason.KEEP_ALIVE)

    def test_timeout_manager_reset_wait_for(self):
        timeout_manager = TimeoutManager()
        # PING frame
        timeout_manager.acknowledge_frame_sent(Frame(Opcode.PING))
        self.assertEqual(timeout_manager._awaited_opcode, Opcode.PONG)
        timeout_manager.acknowledge_frame_receipt(Frame(Opcode.PONG))
        self.assertIsNone(timeout_manager._awaited_opcode)

        # CLOSE frame
        timeout_manager.acknowledge_frame_sent(Frame(Opcode.CLOSE))
        self.assertEqual(timeout_manager._awaited_opcode, Opcode.CLOSE)
        timeout_manager.acknowledge_frame_receipt(Frame(Opcode.CLOSE))
        self.assertIsNone(timeout_manager._awaited_opcode)
