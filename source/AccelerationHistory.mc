import Toybox.Lang;
import Toybox.Sensor;

class AccelerationHistory  {
    private var _sampleRate as Lang.Number = null;
    private var _samples as RingBuffer;
    private var _totalSamples as Lang.Integer = 0;
    private var _callbacks as Lang.Array<Lang.Method> = new[0];

    public function initialize(size as Lang.Number) {
        _sampleRate = Sensor.getMaxSampleRate();
        _samples = new RingBuffer(size);
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
        var zs = data.accelerometerData.z;
        for (var i = 0; i < zs.size(); i++) {
            _samples.append(zs[i]);
        }
        for (var i = 0; i < _callbacks.size(); i++) {
            _callbacks[i].invoke(zs.size());
        }
    }

    public function subscribe(callback as Lang.Method) {
        var newCallbacks = new[_callbacks.size() + 1];
        for (var i = 0; i < _callbacks.size(); i++) {
            newCallbacks[i] = _callbacks[i];
        }
        newCallbacks[newCallbacks.size() - 1] = callback;
        _callbacks = newCallbacks;
    }

    public function getSampleRate() {
        return _sampleRate;
    }

    public function reversed() as RingBufferReverseIterator {
        return new RingBufferReverseIterator(_samples);
    }
}

class RingBuffer {
    private var _maxSize as Lang.Number = 0;
    private var _buffer as Array;
    private var _start as Lang.Number = 0;
    private var _size as Lang.Number = 0;

    public function initialize(maxSize as Lang.Number) {
        _maxSize = maxSize;
        _buffer = new[_maxSize];
    }

    public function append(element) {
        var targetIdx = (_start + _size) % _maxSize;
        if (_size < _maxSize) {
            _size++;
        } else {
            _start = (_start + 1) % _maxSize;
        }
        _buffer[targetIdx] = element;
    }

    public function size() as Lang.Number {
        return _size;
    }

    public function get(idx as Lang.Number) {
        return _buffer[(_start + idx) % _maxSize];
    }
}

class RingBufferReverseIterator {
    private var _ringBuffer as RingBuffer;
    private var _currentIdx as Lang.Number;

    public function initialize(ringBuffer as RingBuffer) {
        _ringBuffer = ringBuffer;
        _currentIdx = _ringBuffer.size() - 1;
    }

    public function next() {
        if (_currentIdx < 0) {
            return null;
        }
        var element = _ringBuffer.get(_currentIdx);
        _currentIdx--;
        return element;
    }
}
