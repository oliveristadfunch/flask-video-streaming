import time
import threading

try:
    from greenlet import getcurrent as get_ident
except ImportError:
    try:
        from thread import get_ident
    except ImportError:
        from _thread import get_ident


class CameraEvent(object):
    """An Event-like class that signals all active clients when a new frame is
    available.
    """

    def __init__(self):
        self.events = {}

    def wait(self):
        """Invoked from each client's thread to wait for the next frame."""
        ident = get_ident()
        if ident not in self.events:
            # this is a new client
            # add an entry for it in the self.events dict
            # each entry has two elements, a threading.Event() and a timestamp
            self.events[ident] = [threading.Event(), time.time()]
        return self.events[ident][0].wait()

    def set(self):
        """Invoked by the camera thread when a new frame is available."""
        now = time.time()
        remove = None
        for ident, event in self.events.items():
            if not event[0].isSet():
                # if this client's event is not set, then set it
                # also update the last set timestamp to now
                event[0].set()
                event[1] = now
            else:
                # if the client's event is already set, it means the client
                # did not process a previous frame
                # if the event stays set for more than 5 seconds, then assume
                # the client is gone and remove it
                if now - event[1] > 5:
                    remove = ident
        if remove:
            del self.events[remove]

    def clear(self):
        """Invoked from each client's thread after a frame was processed."""
        self.events[get_ident()][0].clear()


class BaseCamera(object):
    thread = None  # background thread that reads frames from camera
    frame = None  # current frame is stored here by background thread
    frameList = []
    last_access = 0  # time of last client access to the camera
    event = CameraEvent()

    def __init__(self, delay):
        """Start the background camera thread if it isn't running yet."""
        BaseCamera.delay = int(delay)
        if BaseCamera.thread is None:
            BaseCamera.last_access = time.time()

            # start background frame thread
            BaseCamera.thread = threading.Thread(target=self._thread)
            BaseCamera.thread.start()

            # wait until first frame is available
            BaseCamera.event.wait()

        # if BaseCamera.encodeThread is None:
        #    BaseCamera.thread = threading.Thread(target=self._encodeThread)
        #    BaseCamera.thread.start()

    def get_frame(self):
        """Return the current camera frame."""
        BaseCamera.last_access = time.time()
        # wait for a signal from the camera thread
        BaseCamera.event.wait()
        BaseCamera.event.clear()

        return BaseCamera.frameList.pop()[0]

    @staticmethod
    def frames():
        """ "Generator that returns frames from the camera."""
        raise NotImplementedError("Must be implemented by subclasses.")

    @classmethod
    def _thread(cls):
        """Camera background thread."""
        print("Starting camera thread.")
        frames_iterator = cls.frames()
        for frame, t in frames_iterator:
            BaseCamera.frame = frame
            BaseCamera.frameList.insert(0, (frame, t))

            if (time.time() - BaseCamera.frameList[-1][1]) * 1000 >= BaseCamera.delay:
                BaseCamera.event.set()  # send signal to clients

            time.sleep(0)

            # if there hasn't been any clients asking for frames in
            # the last 10 seconds then stop the thread
            if time.time() - BaseCamera.last_access > 10:
                frames_iterator.close()
                print("Stopping camera thread due to inactivity.")
                break
        BaseCamera.thread = None
