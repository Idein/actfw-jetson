from nose2.tools import params


@params(
    {'from': 'actfw_jetson', 'import': 'Display'},
)
def test_import_actfw_gstreamer(param):
    exec(f'''from {param['from']} import {param['import']}''')
