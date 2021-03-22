import threading
from PIL import Image
from actfw_jetson.logger import DEFAULT_LOGGER
from actfw_core.task import Producer
from actfw_core.capture import Frame


class NVArgusCameraCapture(Producer):
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
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst, GObject
        self._Gst = Gst

        self._logger = logger
        self._pipeline = self._Gst.Pipeline()

        self._camera_in_frames = []

        bus = self._pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::error', self._on_bus_error)

        # define elements
        nvarguscamerasrc = self._Gst.ElementFactory.make('nvarguscamerasrc')

        capsfilter = self._Gst.ElementFactory.make('capsfilter')
        capsfilter.set_property('caps', self._Gst.caps_from_string(
            f'video/x-raw(memory:NVMM),format=NV12,width={size[0]},height={size[1]},framerate={fps}/1'
        ))

        # converts from NV12 into RGBA
        nvvidconv = self._Gst.ElementFactory.make('nvvidconv')
        capsfilter = self._Gst.ElementFactory.make('capsfilter')
        capsfilter.set_property('caps', self._Gst.caps_from_string(
            'video/x-raw,format=RGBA'
        ))

        appsink = self._Gst.ElementFactory.make('appsink')
        appsink.set_property('emit-signals', True)

        ## add elements
        self._pipeline.add(nvarguscamerasrc)
        self._pipeline.add(capsfilter)
        self._pipeline.add(nvvidconv)
        self._pipeline.add(capsfilter)
        self._pipeline.add(appsink)

        ## link elements
        nvarguscamerasrc.link(capsfilter)
        capsfilter.link(nvvidconv)
        nvvidconv.link(capsfilter)
        capsfilter.link(appsink)

        ## subscribe to <new-sample> signal
        appsink.connect("new-sample", NVArguesCameraCapture._appsink_on_new_sample, self)

        self._pipeline.set_state(self._Gst.State.PLAYING)

        self._glib_loop = GObject.MainLoop()
        threading.Thread(target=self._glib_loop.run).start()

    def run(self):
        # _appsink_on_new_sample produces frames
        pass

    def stop(self):
        self._pipeline.set_state(self._Gst.State.NULL)
        self._glib_loop.quit()

    @classmethod
    def _appsink_on_new_sample(sink, slf):
        # Emit 'pull-sample' signal
        # https://lazka.github.io/pgi-docs/GstApp-1.0/classes/AppSink.html#GstApp.AppSink.signals.pull_sample
        sample = sink.emit("pull-sample")

        if isinstance(sample, Gst.Sample):
            array = extract_buffer(sample)

            im = Image.fromarray(np.uint8(array))
            frame = Frame(im)
            if slf._outlet(frame):
                slf._camera_in_frames.append(frame)

            return Gst.FlowReturn.OK

        return Gst.FlowReturn.ERROR

    def _on_bus_error(self, bus, msg):
        self._logger.error('on_error():', msg.parse_error())
