using Toybox.ActivityRecording;
using Toybox.Lang;

class Recorder  {
    private var _history as AccelerationHistory;
    private var _session as ActivityRecording.Session? = null;
    private var _fields as Lang.Array<FitContributor.Field> = new[0];

    public function initialize(history as AccelerationHistory) {
        _history = history;
        _history.subscribe(method(:update));
    }

    public function update(numNew as Lang.Number) as Void {
        var reversedHistory = _history.reversed();
        for (var i = _fields.size() - 1; i >= 0; i--) {
            var value = reversedHistory.next();
            if (value == null) {
                break;
            }
            _fields[i].setData(value);
        }
    }

    public function toggleRecording() as Boolean {
        if (_session == null) {
            _session = ActivityRecording.createSession({
                :name=>"Bumps",
                :sport=>ActivityRecording.SPORT_CYCLING,
                :subSport=>ActivityRecording.SUB_SPORT_ROAD});
            var numFields = _history.getSampleRate();
            if (numFields > 16) {
                // TODO We're apparently not allowed more than 16 fields, need a workaround.
                numFields = 16;
            }
            _fields = new[numFields];
            for (var i = 0; i < _fields.size(); i++) {
                var field = _session.createField(Lang.format("accel_z_$1$", [i]), i, FitContributor.DATA_TYPE_SINT32, {});
                _fields[i] = field;
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
