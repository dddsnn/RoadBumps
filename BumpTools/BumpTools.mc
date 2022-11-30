import Toybox.ActivityRecording;
import Toybox.Lang;
import Toybox.Math;
import Toybox.Position;
import Toybox.Sensor;

module BumpTools {
    public function min(a, b) {
        if (a <= b) {
            return a;
        }
        return b;
    }

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

        public function close() as Void {
            Sensor.unregisterSensorDataListener();
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

    function sampleAsInt16(sample as Lang.Number?) as Lang.Number {
        if (sample == null) {
            return -32768;
        }
        if (sample < -32767) {
            return -32767;
        }
        if (sample > 32767) {
            return 32767;
        }
        return sample;
    }

    public function radToSemicircles(rad as Lang.Float) as Lang.Number {
        return ((rad * 0x80000000) / Math.PI).toNumber();
    }

    class Recorder  {
        const SAMPLES_PER_FIELD as Lang.Number = 8;
        private var _history as AccelerationHistory;
        private var _session as ActivityRecording.Session? = null;
        private var _accelFields as Lang.Array<FitContributor.Field> = new[0];
        private var _timestampField as FitContributor.Field = null;
        private var _latField as FitContributor.Field = null;
        private var _longField as FitContributor.Field = null;
        private var _speedField as FitContributor.Field = null;

        public function initialize(history as AccelerationHistory) {
            _history = history;
            _history.subscribe(method(:onAccel));
            Position.enableLocationEvents(
                Position.LOCATION_CONTINUOUS, method(:onPosition));
        }

        public function onAccel(numNew as Lang.Number) as Void {
            var historyIter = _history.iter();
            for (var i = 0; i < _accelFields.size(); i++) {
                var fieldData = new Array<Lang.Number?>[SAMPLES_PER_FIELD];
                for (var j = 0; j < SAMPLES_PER_FIELD; j++) {
                    // The iterator returns nulls when empty. Those will be
                    // encoded with a special value.
                    fieldData[j] = sampleAsInt16(historyIter.next());
                }
                _accelFields[i].setData(fieldData);
            }
        }

        public function onPosition(info as Position.Info) as Void {
            if (_session == null) {
                return;
            }
            if (info.when != null) {
                _timestampField.setData(info.when.value());
            }
            if (info.position != null) {
            var rads = info.position.toRadians();
                _latField.setData(radToSemicircles(rads[0]));
                _longField.setData(radToSemicircles(rads[1]));
            }
            if (info.speed != null) {
                _speedField.setData(info.speed.toNumber() * 1000);
            }
        }

        public function toggleRecording() as Void {
            if (_session == null) {
                createSession();
            } else {
                _session.stop();
                _session.save();
                _timestampField = null;
                _latField = null;
                _longField = null;
                _speedField = null;
                _accelFields = new[0];
                _session = null;
            }
        }

        public function isRecording() as Boolean {
            return _session != null;
        }

        private function createSession() {
            _session = ActivityRecording.createSession({
                :name => "Bumps",
                :sport => ActivityRecording.SPORT_CYCLING,
                :subSport => ActivityRecording.SUB_SPORT_ROAD});
            _timestampField = _session.createField(
                "timestamp", 0, FitContributor.DATA_TYPE_UINT32,
                {:nativeNum => 253});
            _latField = _session.createField(
                "lat", 1, FitContributor.DATA_TYPE_SINT32, {:nativeNum => 0});
            _longField = _session.createField(
                "long", 2, FitContributor.DATA_TYPE_SINT32, {:nativeNum => 1});
            _speedField = _session.createField(
                "speed", 3, FitContributor.DATA_TYPE_UINT16,
                {:nativeNum => 6});
            var numFields = _history.getSampleRate() / SAMPLES_PER_FIELD;
            if (_history.getSampleRate() % SAMPLES_PER_FIELD != 0) {
                numFields += 1;
            }
            _accelFields = new[numFields];
            for (var i = 0; i < _accelFields.size(); i++) {
                var fieldName = Lang.format(
                    "accel_z_$1$-$2$",
                    [i * SAMPLES_PER_FIELD, (i + 1) * SAMPLES_PER_FIELD]);
                _accelFields[i] = _session.createField(
                    fieldName, 5 + i, FitContributor.DATA_TYPE_SINT16,
                    {:count => SAMPLES_PER_FIELD});
            }
            _session.start();
        }
    }

    class AccelerationGraph {
        private var _history as AccelerationHistory;
        private var _xOffset as Lang.Number;
        private var _width as Lang.Number;
        private var _height as Lang.Number;
        private var _barWidth as Lang.Number;
        private var _graphLimitMilliG as Lang.Number;
        private var _numBars as Lang.Number;
        private var _centerY as Lang.Number;

        public function initialize(
            history as AccelerationHistory, xOffset as Lang.Number,
            yOffset as Lang.Number, width as Lang.Number,
            height as Lang.Number, barWidth as Lang.Number,
            graphLimitMilliG as Lang.Number) {
            _history = history;
            _xOffset = xOffset;
            _width = width;
            _height = height;
            _barWidth = barWidth;
            _graphLimitMilliG = graphLimitMilliG;
            _numBars = (_width - xOffset) / barWidth;
            _centerY = (_height / 2) + yOffset;
        }

        public function draw(dc as Graphics.Dc) {
            dc.setColor(Graphics.COLOR_RED, Graphics.COLOR_BLACK);
            dc.fillRectangle(_xOffset, _centerY, _width, 1);
            dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_BLACK);
            var reversedHistory = _history.reversed();
            for (var i = 0; i < _numBars; i++) {
                var value = reversedHistory.next();
                if (value == null) {
                    break;
                }
                // Adjust for normal gravity, display idle as 0.
                var adjustedValue = value + 1000;
                var barHeight = (
                    (adjustedValue * (_height / 2)).abs() / _graphLimitMilliG);
                barHeight = min(barHeight, _height / 2);
                var y = _centerY;
                if (adjustedValue > 0) {
                    y -= barHeight;
                }
                dc.fillRectangle(
                    _width - ((i + 1) * _barWidth), y, _barWidth, barHeight);
            }
        }
    }
}
