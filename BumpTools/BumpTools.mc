import Toybox.ActivityRecording;
import Toybox.Lang;
import Toybox.Sensor;

module BumpTools {
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

        public function iter() as RingBufferIterator {
            return new RingBufferIterator(_samples);
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

    class RingBufferIterator {
        private var _ringBuffer as RingBuffer;
        private var _currentIdx as Lang.Number;

        public function initialize(ringBuffer as RingBuffer) {
            _ringBuffer = ringBuffer;
            _currentIdx = 0;
        }

        public function next() {
            if (_currentIdx >= _ringBuffer.size()) {
                return null;
            }
            var element = _ringBuffer.get(_currentIdx);
            _currentIdx++;
            return element;
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

    function sampleAsInt16(sample as Lang.Number) as Lang.Number {
        if (sample < -32768) {
            return -32768;
        }
        if (sample > 32767) {
            return 32767;
        }
        return sample;
    }

    class Recorder  {
        const SAMPLES_PER_FIELD as Lang.Number = 8;
        private var _history as AccelerationHistory;
        private var _session as ActivityRecording.Session? = null;
        private var _fields as Lang.Array<FitContributor.Field> = new[0];

        public function initialize(history as AccelerationHistory) {
            _history = history;
            _history.subscribe(method(:update));
        }

        public function update(numNew as Lang.Number) as Void {
            var historyIter = _history.iter();
            for (var i = 0; i < _fields.size(); i++) {
                var fieldData = new Array<Lang.Number>[SAMPLES_PER_FIELD];
                for (var j = 0; j < SAMPLES_PER_FIELD; j++) {
                    var sample = historyIter.next();
                    if (sample == null) {
                        _fields[i].setData(fieldData);
                        return;
                    }
                    fieldData[j] = sampleAsInt16(sample);
                }
                _fields[i].setData(fieldData);
            }
        }

        public function toggleRecording() as Boolean {
            if (_session == null) {
                _session = ActivityRecording.createSession({
                    :name => "Bumps",
                    :sport => ActivityRecording.SPORT_CYCLING,
                    :subSport => ActivityRecording.SUB_SPORT_ROAD});
                var numFields = _history.getSampleRate() / SAMPLES_PER_FIELD;
                if (_history.getSampleRate() % SAMPLES_PER_FIELD != 0) {
                    numFields += 1;
                }
                _fields = new[numFields];
                for (var i = 0; i < _fields.size(); i++) {
                    _fields[i] = _session.createField(Lang.format("accel_z_$1$-$2$", [i * SAMPLES_PER_FIELD, (i + 1) * SAMPLES_PER_FIELD]), i, FitContributor.DATA_TYPE_SINT16, {:count => SAMPLES_PER_FIELD});
                }
                _session.start();
                return true;
            } else {
                _session.stop();
                _session.save();
                _fields = new[0];
                _session = null;
                return false;
            }
        }
    }
}
