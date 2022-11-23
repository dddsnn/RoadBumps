using Toybox.ActivityRecording;
using Toybox.Lang;

private function sampleAsInt16(sample as Lang.Number) as Lang.Number {
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
