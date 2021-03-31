import threading

from actfw_core.capture import Frame
from actfw_core.task import Producer
from actfw_jetson.logger import DEFAULT_LOGGER
from PIL import Image


class NVArgusCameraCapture(Producer):  # type: ignore
    """Camera using nvarguscamerasrc plugin.

    Outputs :class:`~actfw_core.capture.Frame` whose content value is PIL.Image.
    """

    def __init__(self, size, fps, logger=DEFAULT_LOGGER):
        """
        Args:
            size (int, int): capture area resolution
            fps (int): framerate
        """
        import gi

        gi.require_version("Gst", "1.0")
        from gi.repository import GObject, Gst

        self._Gst = Gst

        super(NVArgusCameraCapture, self).__init__()

        self._logger = logger
        self._pipeline = self._Gst.Pipeline()

        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::error", self._on_bus_error)

        # define elements
        nvarguscamerasrc = self._Gst.ElementFactory.make("nvarguscamerasrc")

        capsfilter1 = self._Gst.ElementFactory.make("capsfilter")
        capsfilter1.set_property(
            "caps",
            self._Gst.caps_from_string(
                f"video/x-raw(memory:NVMM),format=NV12,width={size[0]},height={size[1]},framerate={fps}/1"
            ),
        )

        # converts from NV12 into RGBA to use input data of PIL.Image.frombytes.
        nvvidconv = self._Gst.ElementFactory.make("nvvidconv")
        capsfilter2 = self._Gst.ElementFactory.make("capsfilter")
        capsfilter2.set_property("caps", self._Gst.caps_from_string("video/x-raw,format=RGBA"))

        appsink = self._Gst.ElementFactory.make("appsink")
        appsink.set_property("emit-signals", True)

        # add elements
        self._pipeline.add(nvarguscamerasrc)
        self._pipeline.add(capsfilter1)
        self._pipeline.add(nvvidconv)
        self._pipeline.add(capsfilter2)
        self._pipeline.add(appsink)

        # link elements
        nvarguscamerasrc.link(capsfilter1)
        capsfilter1.link(nvvidconv)
        nvvidconv.link(capsfilter2)
        capsfilter2.link(appsink)

        # subscribe to <new-sample> signal
        appsink.connect("new-sample", _appsink_on_new_sample, self)

        self._pipeline.set_state(self._Gst.State.PLAYING)

        self._glib_loop = GObject.MainLoop()
        threading.Thread(target=self._glib_loop.run).start()

    def run(self):
        # _appsink_on_new_sample produces frames
        pass

    def stop(self):
        self._pipeline.set_state(self._Gst.State.NULL)
        self._glib_loop.quit()

    def _on_bus_error(self, bus, msg):
        self._logger.error("on_error():", msg.parse_error())


def _appsink_on_new_sample(sink, slf):
    # Emit 'pull-sample' signal
    # https://lazka.github.io/pgi-docs/GstApp-1.0/classes/AppSink.html#GstApp.AppSink.signals.pull_sample
    sample = sink.emit("pull-sample")

    if isinstance(sample, slf._Gst.Sample):
        im = _extract_buffer(sample)
        frame = Frame(im)
        slf._outlet(frame)
        return slf._Gst.FlowReturn.OK

    return slf._Gst.FlowReturn.ERROR


def _extract_buffer(sample):
    """Extracts Gst.Buffer from Gst.Sample and converts to PIL.Image"""

    buffer = sample.get_buffer()  # Gst.Buffer
    caps_format = sample.get_caps().get_structure(0)  # Gst.Structure
    w, h = caps_format.get_value("width"), caps_format.get_value("height")

    buffer_size = buffer.get_size()
    return Image.frombuffer("RGBA", (w, h), buffer.extract_dup(0, buffer_size))
