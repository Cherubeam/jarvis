"""Unit tests for InProcessBroker."""

import pytest
import threading
import time

from packages.core.broker import InProcessBroker


@pytest.mark.unit
class TestInProcessBroker:

    def test_publish_subscribe(self):
        broker = InProcessBroker()
        received = []

        def consumer():
            for msg in broker.subscribe("topic-1", "group-1"):
                received.append(msg)
                if msg.get("stop"):
                    break

        t = threading.Thread(target=consumer, daemon=True)
        t.start()

        time.sleep(0.2)  # Let subscriber start
        broker.publish("topic-1", {"data": "hello"})
        broker.publish("topic-1", {"data": "world", "stop": True})

        t.join(timeout=3.0)
        assert len(received) == 2
        assert received[0]["data"] == "hello"
        assert received[1]["data"] == "world"

    def test_multiple_subscribers(self):
        broker = InProcessBroker()
        received_1 = []
        received_2 = []

        def consumer(group, results):
            for msg in broker.subscribe("topic", group):
                results.append(msg)
                if msg.get("stop"):
                    break

        t1 = threading.Thread(target=consumer, args=("g1", received_1), daemon=True)
        t2 = threading.Thread(target=consumer, args=("g2", received_2), daemon=True)
        t1.start()
        t2.start()

        time.sleep(0.2)
        broker.publish("topic", {"data": "msg", "stop": True})

        t1.join(timeout=3.0)
        t2.join(timeout=3.0)

        assert len(received_1) == 1
        assert len(received_2) == 1

    def test_ack_is_noop(self):
        broker = InProcessBroker()
        broker.ack("topic", "group", "msg-1")  # No error

    def test_close_clears_queues(self):
        broker = InProcessBroker()
        # Subscribe to create a queue
        t = threading.Thread(
            target=lambda: next(iter(broker.subscribe("t", "g")), None),
            daemon=True,
        )
        t.start()
        time.sleep(0.1)
        broker.close()
        assert len(broker._queues) == 0
