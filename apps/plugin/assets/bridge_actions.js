.pragma library

// Action kinds exposed to Python -> score_operations command names.
var ACTION_TO_OP = {
    add_note: "addNote",
    add_chord: "addChord",
    add_rest: "addRest",
    write_sequence: "writeSequence",
    modify_note: "modifyNote",
    modify_chord: "modifyChord",
    append_measures: "appendMeasures",
    add_part: "addPart",
    set_header_text: "setHeaderText",
    set_meta_tag: "setMetaTag",
    add_time_signature: "addTimeSignature",
    add_key_signature: "addKeySignature",
    add_clef: "addClef",
    add_tempo: "addTempo",
    add_dynamic: "addDynamic",
    add_articulation: "addArticulation",
    add_fermata: "addFermata",
    add_arpeggio: "addArpeggio",
    add_staff_text: "addStaffText",
    add_system_text: "addSystemText",
    add_rehearsal_mark: "addRehearsalMark",
    add_expression_text: "addExpressionText",
    add_lyrics: "addLyrics",
    write_lyrics: "writeLyrics",
    add_harmony: "addHarmony",
    add_fingering: "addFingering",
    add_breath: "addBreath",
    add_tuplet: "addTuplet",
    add_layout_break: "addLayoutBreak",
    add_spacer: "addSpacer",
    modify_measure: "modifyMeasure"
}

var ACTION_SPECS = [
    { kind: "add_note", op: "addNote", summary: "Add one note at tick/staff/voice." },
    { kind: "add_chord", op: "addChord", summary: "Add one chord at tick/staff/voice." },
    { kind: "add_rest", op: "addRest", summary: "Add one rest at tick/staff/voice." },
    { kind: "write_sequence", op: "writeSequence", summary: "Sequentially write note/chord/rest events." },
    { kind: "modify_note", op: "modifyNote", summary: "Modify note properties at a chord position." },
    { kind: "modify_chord", op: "modifyChord", summary: "Modify chord/rest properties at a position." },
    { kind: "append_measures", op: "appendMeasures", summary: "Append empty measures to the score." },
    { kind: "add_part", op: "addPart", summary: "Append an instrument part." },
    { kind: "set_header_text", op: "setHeaderText", summary: "Set title/composer/etc header text." },
    { kind: "set_meta_tag", op: "setMetaTag", summary: "Set score meta tags." },
    { kind: "add_time_signature", op: "addTimeSignature", summary: "Insert a time signature." },
    { kind: "add_key_signature", op: "addKeySignature", summary: "Insert a key signature." },
    { kind: "add_clef", op: "addClef", summary: "Insert a clef element." },
    { kind: "add_tempo", op: "addTempo", summary: "Insert a tempo text element." },
    { kind: "add_dynamic", op: "addDynamic", summary: "Insert a dynamic marking." },
    { kind: "add_articulation", op: "addArticulation", summary: "Insert articulation on a note/chord." },
    { kind: "add_fermata", op: "addFermata", summary: "Insert fermata on a note/chord." },
    { kind: "add_arpeggio", op: "addArpeggio", summary: "Insert arpeggio on a chord." },
    { kind: "add_staff_text", op: "addStaffText", summary: "Insert staff text." },
    { kind: "add_system_text", op: "addSystemText", summary: "Insert system text." },
    { kind: "add_rehearsal_mark", op: "addRehearsalMark", summary: "Insert rehearsal mark." },
    { kind: "add_expression_text", op: "addExpressionText", summary: "Insert expression text below staff." },
    { kind: "add_lyrics", op: "addLyrics", summary: "Insert a lyrics syllable at position." },
    { kind: "write_lyrics", op: "writeLyrics", summary: "Write lyrics syllables across subsequent notes." },
    { kind: "add_harmony", op: "addHarmony", summary: "Chord-symbol action (currently blocked for safety in MS4)." },
    { kind: "add_fingering", op: "addFingering", summary: "Insert fingering text." },
    { kind: "add_breath", op: "addBreath", summary: "Insert a breath mark." },
    { kind: "add_tuplet", op: "addTuplet", summary: "Create a tuplet container." },
    { kind: "add_layout_break", op: "addLayoutBreak", summary: "Insert line/page/section break." },
    { kind: "add_spacer", op: "addSpacer", summary: "Insert a spacer element." },
    { kind: "modify_measure", op: "modifyMeasure", summary: "Update repeat/stretch/irregular measure properties." }
]

function listActionSpecs() {
    return ACTION_SPECS
}

function toCommand(action) {
    if (!action || typeof action !== "object")
        throw new Error("Action must be an object")

    var kind = action.kind
    var op = ACTION_TO_OP[kind]
    if (!op)
        throw new Error("Unsupported action kind: " + kind)

    var cmd = { op: op }
    var target = action.target || {}

    var staffVal = firstDefined(action.staffIdx, action.staff, target.staffIdx, target.staff)
    if (staffVal !== undefined && staffVal !== null) cmd.staffIdx = staffVal

    var voiceVal = firstDefined(action.voice, target.voice)
    if (voiceVal !== undefined && voiceVal !== null) cmd.voice = voiceVal

    var tickVal = firstDefined(action.tick, target.tick)
    if (tickVal !== undefined && tickVal !== null) cmd.tick = tickVal

    if (target.measure !== undefined && action.measure === undefined) cmd.measure = target.measure

    var skip = {
        kind: true,
        target: true,
        staff: true,
        staffIdx: true,
        voice: true,
        tick: true
    }

    for (var key in action) {
        if (!skip[key]) cmd[key] = action[key]
    }

    return cmd
}

function firstDefined() {
    for (var i = 0; i < arguments.length; i++) {
        if (arguments[i] !== undefined && arguments[i] !== null)
            return arguments[i]
    }
    return undefined
}
