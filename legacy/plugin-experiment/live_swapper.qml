import QtQuick 2.9
import MuseScore 3.0

MuseScore {
    menuPath:      "Plugins.Live Swapper"
    description:   "Delete all notes or add a single note in-place."
    version:       "1.0"
    pluginType:    "dialog"
    requiresScore: false

    width:  340
    height: 220

    property string statusMsg: "Ready"

    function deleteAll() {
        var cursor = curScore.newCursor()

        // Phase 1: collect positions and durations as plain data (no element refs).
        // Element references become stale once the score is modified, so we only
        // keep primitive values that stay valid across the edit.
        var chords = []
        for (var track = 0; track < curScore.ntracks; track++) {
            cursor.track = track
            cursor.rewind(Cursor.SCORE_START)
            while (cursor.segment) {
                var el = cursor.element
                if (el && el.type === Element.CHORD) {
                    chords.push({
                        fraction: el.fraction,
                        durN:     el.duration.numerator,
                        durD:     el.duration.denominator,
                        track:    track
                    })
                }
                cursor.next()
            }
        }

        if (chords.length === 0) {
            statusMsg = "No notes to delete"
            return
        }

        // Phase 2: stamp a rest over every chord position using cursor.addRest().
        // addRest() overwrites whatever is at the cursor position with a rest of
        // the duration set by setDuration() — no gaps, no element invalidation.
        curScore.startCmd()
        for (var i = 0; i < chords.length; i++) {
            var c = chords[i]
            cursor.track = c.track
            cursor.rewindToFraction(c.fraction)
            cursor.setDuration(c.durN, c.durD)
            cursor.addRest()
        }
        curScore.endCmd()

        statusMsg = "Deleted " + chords.length + " chords"
    }

    function addNote() {
        var cursor = curScore.newCursor()
        cursor.staffIdx = 0
        cursor.voice = 0
        cursor.rewind(Cursor.SCORE_START)
        cursor.setDuration(1, 4)
        curScore.startCmd()
        cursor.addNote(60)
        curScore.endCmd()
        statusMsg = "Added middle C"
    }

    Rectangle {
        x: 0; y: 0
        width:  340
        height: 220
        color:  "#1e1e2e"

        Text {
            x: 0; y: 22
            width: 340
            horizontalAlignment: Text.AlignHCenter
            text:  "Live Swapper"
            color: "#cdd6f4"
            font.pixelSize: 20
            font.bold: true
        }

        Rectangle {
            x: 20; y: 70
            width: 140; height: 52
            radius: 5
            color: btn1.pressed ? "#5a1010" : "#7a2020"
            Text {
                anchors.centerIn: parent
                text:  "Delete All"
                color: "#ffffff"
                font.pixelSize: 14
                font.bold: true
            }
            MouseArea {
                id: btn1
                anchors.fill: parent
                onClicked: deleteAll()
            }
        }

        Rectangle {
            x: 180; y: 70
            width: 140; height: 52
            radius: 5
            color: btn2.pressed ? "#105a10" : "#207a20"
            Text {
                anchors.centerIn: parent
                text:  "Add Note"
                color: "#ffffff"
                font.pixelSize: 14
                font.bold: true
            }
            MouseArea {
                id: btn2
                anchors.fill: parent
                onClicked: addNote()
            }
        }

        Rectangle {
            x: 20; y: 142
            width: 300; height: 40
            radius: 5
            color: "#2a2a3e"
            Text {
                anchors.centerIn: parent
                text:  statusMsg
                color: "#a6adc8"
                font.pixelSize: 13
            }
        }
    }

    onRun: {}
}
