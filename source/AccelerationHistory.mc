import Toybox.Lang;
import Toybox.Sensor;

class AccelerationHistory  {
    private var _sampleRate as Lang.Number = null;
    private var _totalSamples as Lang.Integer = 0;
    private var _lastY as Lang.Number = null;

    public function initialize() {
        _sampleRate = Sensor.getMaxSampleRate();
        var options = {
            :period => 1,
            :accelerometer => {
                :enabled => true,
                :sampleRate => _sampleRate
            },
            :heartBeatIntervals => {
                :enabled => false
            }
        };
        Sensor.registerSensorDataListener(method(:append), options);
    }

    public function append(data as Sensor.SensorData) {
        if (data.accelerometerData == null) {
            return;
        }
        var ys = data.accelerometerData.y;
        for (var i = 0; i < ys.size(); i++) {
            _totalSamples++;
            var y = ys[i];
            _lastY = y;
        }
    }

    public function getSampleRate() {
        return _sampleRate;
    }

    public function getLastY() {
        return _lastY;
    }
}
