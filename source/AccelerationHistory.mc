import Toybox.Sensor;

class AccelerationHistory  {
    private var _accel as Array<Float>;
    private var _i = 0;

    public function initialize() {
        _accel = new Array<Float>[3];
    }

    public function get() {
        _i += 1;
        return _i;
    }
}
