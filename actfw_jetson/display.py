import threading

from actfw_jetson.logger import DEFAULT_LOGGER
from PIL import Image


class Display:
    """Display using nvoverlaysink plugin"""

    def __init__(self, size, fps, logger=DEFAULT_LOGGER):
        """
        Args:
            size (int, int): display area resolution
            fps (int): framerate
        """
        import gi

        gi.require_version("Gst", "1.0")
        from gi.repository import GObject, Gst

        self._Gst = Gst

        self._logger = logger
        self._pipeline = self._Gst.Pipeline()

        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message::error", Display._on_bus_error)

        # define elements
        self._appsrc = self._Gst.ElementFactory.make("appsrc")
        self._appsrc.set_property("is-live", True)
        self._appsrc.set_property("block", True)

        capsfilter1 = self._Gst.ElementFactory.make("capsfilter")
        capsfilter1.set_property(
            "caps", self._Gst.caps_from_string(f"video/x-raw,format=RGBA,width={size[0]},height={size[1]},framerate={fps}/1")
        )

        nvvidconv = self._Gst.ElementFactory.make("nvvidconv")

        capsfilter2 = self._Gst.ElementFactory.make("capsfilter")
        capsfilter2.set_property("caps", self._Gst.caps_from_string("video/x-raw(memory:NVMM),format=NV12"))

        nvoverlaysink = self._Gst.ElementFactory.make("nvoverlaysink")

        # add elements
        self._pipeline.add(self._appsrc)
        self._pipeline.add(capsfilter1)
        self._pipeline.add(nvvidconv)
        self._pipeline.add(capsfilter2)
        self._pipeline.add(nvoverlaysink)

        # link elements
        self._appsrc.link(capsfilter1)
        capsfilter1.link(nvvidconv)
        nvvidconv.link(capsfilter2)
        capsfilter2.link(nvoverlaysink)

        self._pipeline.set_state(self._Gst.State.PLAYING)

        self._glib_loop = GObject.MainLoop()
        threading.Thread(target=self._glib_loop.run).start()

    def update(self, src_im: Image) -> "Gst.FlowReturn":  # type: ignore  # noqa F821
        """
        Update display.

        Args:
            src_im (PIL.Image): update image (RGB)
        """
        gst_buffer = self._im_to_gst_buffer(src_im)
        self._appsrc.emit("push-buffer", gst_buffer)
        return self._Gst.FlowReturn.OK

    def stop(self):
        self._pipeline.set_state(self._Gst.State.NULL)
        self._glib_loop.quit()

    def _on_bus_error(self, bus: "Gst.Bus", msg: "Gst.Message") -> None:  # type: ignore  # noqa F821
        self._logger.error("on_error():", msg.parse_error())

    def _im_to_gst_buffer(self, im: Image) -> "Gst.Buffer":  # type: ignore  # noqa F821
        """Converts PIL Image (RGB) to Gst.Buffer (RGBA)"""
        im.putalpha(255)
        return self._Gst.Buffer.new_wrapped(im.tobytes())
