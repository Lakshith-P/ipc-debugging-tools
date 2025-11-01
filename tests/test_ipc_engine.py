import unittest
import multiprocessing as mp
from ipc_engine import QueueChannel


class TestQueueChannel(unittest.TestCase):
    def test_send_recv(self):
        ch = QueueChannel()
        # Send two messages
        ch.send(0, "msg1")
        ch.send(1, "msg2")

        # Receive messages (order preserved in Queue)
        m1 = ch.recv(0)
        m2 = ch.recv(1)

        self.assertIsNotNone(m1)
        self.assertIsNotNone(m2)
        self.assertEqual(m1.data, "msg1")
        self.assertEqual(m2.data, "msg2")


if __name__ == "__main__":
    mp.set_start_method("spawn", force=False)
    unittest.main()
