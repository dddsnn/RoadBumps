//
// Copyright 2016-2021 by Garmin Ltd. or its subsidiaries.
// Subject to Garmin SDK License Agreement and Wearables
// Application Developer Agreement.
//

import Toybox.Lang;
import Toybox.WatchUi;

class BumpRecorderDelegate extends WatchUi.BehaviorDelegate {
    private var _parentView as BumpRecorderView;

    public function initialize(view as BumpRecorderView) {
        BehaviorDelegate.initialize();
        _parentView = view;
    }

    public function onSelect() as Boolean {
        return true;
    }
}
