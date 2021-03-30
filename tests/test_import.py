from nose2.tools import params


@params(
    {'from': 'actfw_jetson', 'import': 'Display'},
    {'from': 'actfw_jetson', 'import': 'NVArgusCameraCapture'},
)
def test_import_actfw_gstreamer(param):
    exec(f'''from {param['from']} import {param['import']}''')
