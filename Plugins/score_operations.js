.pragma library

// ============================================================================
// score_operations.js — Maestro Operations Library (v4)
// ============================================================================
//
// Comprehensive operations for AI-driven score composition in MuseScore 4.
//
// IMPORTANT — MS4 Plugin API Limitations:
//   - Spanners (slurs, hairpins, ottava, pedal, trill, volta, textlines,
//     glissando) CANNOT be added via newElement + cursor.add(). The C++
//     Cursor::add() method has no case for spanners — they crash or produce
//     broken output. These must be added manually by the user for now.
//   - Barlines cannot be created via newElement. Existing barlines must be
//     found and modified instead.
//   - Notes must use cursor.addNote(pitch), not newElement(Element.NOTE).
//   - cmd() does not work reliably from pluginType:"dialog" plugins.
//
// .pragma library — no access to QML globals (Element enum, etc).
// The QML host passes an elTypes map with real enum values.
//
// Import in QML:  import "score_operations.js" as Ops
// ============================================================================


// ─── Duration Helpers ───────────────────────────────────────────────────────

var DURATIONS = {
    "whole": [1,1], "half": [1,2], "quarter": [1,4], "eighth": [1,8],
    "16th": [1,16], "32nd": [1,32], "64th": [1,64]
}

function durationFraction(name, dots) {
    dots = dots || 0
    var base = DURATIONS[name]
    if (!base) return [1, 4]
    var n = base[0], d = base[1]
    if (dots === 0) return [n, d]
    var multN = Math.pow(2, dots + 1) - 1
    var multD = Math.pow(2, dots)
    n = n * multN; d = d * multD
    var g = gcd(n, d)
    return [n / g, d / g]
}

function gcd(a, b) {
    a = Math.abs(a); b = Math.abs(b)
    while (b) { var t = b; b = a % b; a = t }
    return a
}


// ─── Pitch Helpers ──────────────────────────────────────────────────────────

// "C4" -> 60, "F#5" -> 78, "Bb3" -> 58
function pitchFromName(name) {
    var noteMap = { "C":0,"D":2,"E":4,"F":5,"G":7,"A":9,"B":11 }
    var match = name.match(/^([A-Ga-g])(#{0,2}|b{0,2})(\d+)$/)
    if (!match) return 60
    var pitch = noteMap[match[1].toUpperCase()] + (parseInt(match[3]) + 1) * 12
    for (var i = 0; i < match[2].length; i++)
        pitch += (match[2][i] === '#') ? 1 : -1
    return pitch
}

function pitchToName(pitch) {
    var names = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
    return names[pitch % 12] + (Math.floor(pitch / 12) - 1)
}

function resolvePitch(p) {
    return (typeof p === "string") ? pitchFromName(p) : p
}

// Convert duration name to ticks (default 480 tpq)
function durationToTicks(durName, dots, tpq) {
    tpq = tpq || 480
    var tickMap = {
        "whole": tpq*4, "half": tpq*2, "quarter": tpq, "eighth": tpq/2,
        "16th": tpq/4, "32nd": tpq/8, "64th": tpq/16
    }
    var baseTicks = tickMap[durName] || tpq
    if (dots && dots > 0)
        baseTicks = baseTicks * ((Math.pow(2, dots+1) - 1) / Math.pow(2, dots))
    return Math.round(baseTicks)
}


// ─── Reference Constants ────────────────────────────────────────────────────

// Key signatures: name -> number (negative = flats, positive = sharps)
var KEYS = {
    "Cb":-7, "Gb":-6, "Db":-5, "Ab":-4, "Eb":-3, "Bb":-2, "F":-1,
    "C":0, "G":1, "D":2, "A":3, "E":4, "B":5, "F#":6, "C#":7
}

// Common instrument IDs for score.appendPart()
var INSTRUMENTS = {
    // Woodwinds
    piccolo:"piccolo", flute:"flute", oboe:"oboe", english_horn:"english-horn",
    clarinet:"clarinet", bass_clarinet:"bass-clarinet", bassoon:"bassoon",
    contrabassoon:"contrabassoon", recorder:"recorder",
    alto_sax:"alto-saxophone", tenor_sax:"tenor-saxophone",
    bari_sax:"baritone-saxophone", soprano_sax:"soprano-saxophone",
    // Brass
    trumpet:"trumpet", horn:"horn", trombone:"trombone",
    bass_trombone:"bass-trombone", tuba:"tuba", euphonium:"euphonium",
    cornet:"cornet", flugelhorn:"flugelhorn",
    // Strings
    violin:"violin", viola:"viola", cello:"violoncello",
    contrabass:"contrabass", harp:"harp",
    // Keyboards
    piano:"piano", harpsichord:"harpsichord", organ:"organ",
    celesta:"celesta", accordion:"accordion",
    // Plucked
    guitar_nylon:"cavaquinho", guitar_steel:"guitar-steel",
    electric_guitar:"electric-guitar", bass_guitar:"bass-guitar",
    ukulele:"ukulele", banjo:"banjo", mandolin:"mandolin",
    // Percussion
    timpani:"timpani", xylophone:"xylophone", marimba:"marimba",
    vibraphone:"vibraphone", glockenspiel:"glockenspiel",
    tubular_bells:"tubular-bells", snare_drum:"snare-drum",
    bass_drum:"bass-drum", drumset:"drumset",
    // Voice
    soprano:"soprano", mezzo_soprano:"mezzo-soprano", alto:"alto",
    tenor:"tenor", baritone:"baritone", bass_voice:"bass"
}


// ─── Sequential Writer ──────────────────────────────────────────────────────
// Auto-advancing cursor for writing melodies/parts without manual tick math.
//
// Usage:
//   var w = Ops.createWriter(score, 0, 0)
//   w.note("C4", "quarter")
//   w.note("E4", "eighth")
//   w.rest("eighth")
//   w.chord(["C4","E4","G4"], "half")

function createWriter(score, staffIdx, voice) {
    var cursor = score.newCursor()
    cursor.staffIdx = staffIdx || 0
    cursor.voice = voice || 0
    cursor.rewind(0)

    return {
        cursor: cursor,
        seekTick: function(tick) { cursor.rewindToTick(tick) },
        seekMeasure: function(idx) {
            cursor.rewind(0)
            for (var i = 0; i < idx; i++) if (!cursor.nextMeasure()) break
        },
        note: function(pitch, durName, dots) {
            var dur = durationFraction(durName, dots)
            cursor.setDuration(dur[0], dur[1])
            cursor.addNote(resolvePitch(pitch))
        },
        chord: function(pitches, durName, dots) {
            if (!pitches || pitches.length === 0) return
            var dur = durationFraction(durName, dots)
            cursor.setDuration(dur[0], dur[1])
            var saveTick = cursor.tick
            cursor.addNote(resolvePitch(pitches[0]))
            for (var i = 1; i < pitches.length; i++) {
                cursor.rewindToTick(saveTick)
                cursor.addNote(resolvePitch(pitches[i]), true)
            }
        },
        rest: function(durName, dots) {
            var dur = durationFraction(durName, dots)
            cursor.setDuration(dur[0], dur[1])
            cursor.addRest()
        },
        tick: function() { return cursor.tick }
    }
}


// ─── Command Executor ───────────────────────────────────────────────────────
// Executes an array of command objects in one undo step.
// Parameters from QML: newEl, fracFn, removeEl, ET (element type map)

function executeCommands(score, commands, newEl, fracFn, removeEl, ET) {
    score.startCmd()
    var results = []
    for (var i = 0; i < commands.length; i++) {
        try {
            results.push(execOp(score, commands[i], newEl, fracFn, removeEl, ET))
        } catch (e) {
            results.push({ ok: false, error: String(e) })
        }
    }
    score.endCmd()
    return results
}

function execOp(score, cmd, newEl, fracFn, removeEl, ET) {
    var cursor = score.newCursor()
    var staffIdx = cmd.staffIdx || 0
    var voice = cmd.voice || 0
    var tick = cmd.tick || 0

    switch (cmd.op) {

    // =====================================================================
    //  NOTES, RESTS, CHORDS
    // =====================================================================

    case "addNote": {
        cursor.staffIdx = staffIdx; cursor.voice = voice
        cursor.rewindToTick(tick)
        var dur = durationFraction(cmd.duration || "quarter", cmd.dots || 0)
        cursor.setDuration(dur[0], dur[1])
        cursor.addNote(resolvePitch(cmd.pitch))
        return { ok: true }
    }

    case "addChord": {
        var pitches = cmd.pitches || []
        if (pitches.length === 0) return { ok: false, error: "No pitches" }
        cursor.staffIdx = staffIdx; cursor.voice = voice
        cursor.rewindToTick(tick)
        var dur = durationFraction(cmd.duration || "quarter", cmd.dots || 0)
        cursor.setDuration(dur[0], dur[1])
        cursor.addNote(resolvePitch(pitches[0]))
        for (var j = 1; j < pitches.length; j++) {
            cursor.rewindToTick(tick)
            cursor.addNote(resolvePitch(pitches[j]), true)
        }
        return { ok: true }
    }

    case "addRest": {
        cursor.staffIdx = staffIdx; cursor.voice = voice
        cursor.rewindToTick(tick)
        var dur = durationFraction(cmd.duration || "quarter", cmd.dots || 0)
        cursor.setDuration(dur[0], dur[1])
        cursor.addRest()
        return { ok: true }
    }

    // =====================================================================
    //  SEQUENTIAL WRITING — write a whole part in one command
    // =====================================================================
    //  events: [
    //    { pitch: "C4", duration: "quarter" },          // note
    //    { pitches: ["C4","E4","G4"], duration: "half"}, // chord
    //    { type: "rest", duration: "quarter" }           // rest
    //  ]

    case "writeSequence": {
        var events = cmd.events || []
        var w = createWriter(score, staffIdx, voice)
        if (tick > 0) w.seekTick(tick)
        if (cmd.measure !== undefined) w.seekMeasure(cmd.measure)
        for (var j = 0; j < events.length; j++) {
            var ev = events[j]
            if (ev.type === "rest") {
                w.rest(ev.duration || "quarter", ev.dots || 0)
            } else if (ev.pitches) {
                w.chord(ev.pitches, ev.duration || "quarter", ev.dots || 0)
            } else {
                w.note(resolvePitch(ev.pitch), ev.duration || "quarter", ev.dots || 0)
            }
        }
        return { ok: true }
    }

    // =====================================================================
    //  NOTE / CHORD PROPERTIES — modify existing elements at a position
    // =====================================================================

    case "modifyNote": {
        cursor.staffIdx = staffIdx; cursor.voice = voice
        cursor.rewindToTick(tick)
        var el = cursor.element
        if (!el || !el.notes) return { ok: false, error: "No chord at tick " + tick }
        var note = el.notes[cmd.noteIndex || 0]
        if (!note) return { ok: false, error: "Note index out of range" }
        if (cmd.tpc !== undefined) note.tpc = cmd.tpc
        if (cmd.tpc1 !== undefined) note.tpc1 = cmd.tpc1
        if (cmd.tpc2 !== undefined) note.tpc2 = cmd.tpc2
        if (cmd.veloOffset !== undefined) note.veloOffset = cmd.veloOffset
        if (cmd.tuning !== undefined) note.tuning = cmd.tuning
        if (cmd.small !== undefined) note.small = cmd.small
        if (cmd.ghost !== undefined) note.ghost = cmd.ghost
        if (cmd.play !== undefined) note.play = cmd.play
        if (cmd.headGroup !== undefined) note.headGroup = cmd.headGroup
        if (cmd.headType !== undefined) note.headType = cmd.headType
        if (cmd.accidentalType !== undefined) note.accidentalType = cmd.accidentalType
        return { ok: true }
    }

    case "modifyChord": {
        cursor.staffIdx = staffIdx; cursor.voice = voice
        cursor.rewindToTick(tick)
        var el = cursor.element
        if (!el) return { ok: false, error: "No element at tick " + tick }
        if (cmd.stemDirection !== undefined) el.stemDirection = cmd.stemDirection
        if (cmd.noStem !== undefined) el.noStem = cmd.noStem
        if (cmd.beamMode !== undefined) el.beamMode = cmd.beamMode
        if (cmd.small !== undefined) el.small = cmd.small
        if (cmd.staffMove !== undefined) el.staffMove = cmd.staffMove
        return { ok: true }
    }

    // =====================================================================
    //  SCORE STRUCTURE
    // =====================================================================

    case "appendMeasures": {
        score.appendMeasures(cmd.count || 1)
        return { ok: true }
    }

    case "addPart": {
        if (cmd.musicXmlId) score.appendPartByMusicXmlId(cmd.musicXmlId)
        else score.appendPart(cmd.instrumentId || "piano")
        return { ok: true }
    }

    case "setHeaderText": {
        score.addText(cmd.type || "title", cmd.text || "")
        return { ok: true }
    }

    case "setMetaTag": {
        score.setMetaTag(cmd.tag || "", cmd.value || "")
        return { ok: true }
    }

    // =====================================================================
    //  TIME SIGNATURE
    // =====================================================================

    case "addTimeSignature": {
        if (!newEl || !fracFn) return { ok: false, error: "Missing context" }
        var ts = newEl(ET.TIMESIG)
        ts.timesig = fracFn(cmd.numerator || 4, cmd.denominator || 4)
        cursor.staffIdx = staffIdx; cursor.voice = 0
        cursor.rewindToTick(tick)
        cursor.add(ts)
        return { ok: true }
    }

    // =====================================================================
    //  KEY SIGNATURE
    // =====================================================================

    case "addKeySignature": {
        if (!newEl) return { ok: false, error: "Missing newElement" }
        var ks = newEl(ET.KEYSIG)
        var keyVal = cmd.key
        if (typeof keyVal === "string") keyVal = KEYS[keyVal] || 0
        ks.key = keyVal
        cursor.staffIdx = staffIdx; cursor.voice = 0
        cursor.rewindToTick(tick)
        cursor.add(ks)
        return { ok: true }
    }

    // =====================================================================
    //  CLEF
    // =====================================================================

    case "addClef": {
        if (!newEl) return { ok: false, error: "Missing newElement" }
        var clef = newEl(ET.CLEF)
        if (cmd.clefType !== undefined) clef.subtype = cmd.clefType
        cursor.staffIdx = staffIdx; cursor.voice = 0
        cursor.rewindToTick(tick)
        cursor.add(clef)
        return { ok: true }
    }

    // =====================================================================
    //  TEMPO
    // =====================================================================

    case "addTempo": {
        if (!newEl) return { ok: false, error: "Missing newElement" }
        var tempo = newEl(ET.TEMPO_TEXT)
        tempo.tempo = (cmd.bpm || 120) / 60.0
        tempo.tempoFollowText = false
        tempo.text = cmd.text || ("\u2669 = " + (cmd.bpm || 120))
        cursor.staffIdx = staffIdx; cursor.voice = 0
        cursor.rewindToTick(tick)
        cursor.add(tempo)
        return { ok: true }
    }

    // =====================================================================
    //  DYNAMICS
    // =====================================================================

    case "addDynamic": {
        if (!newEl) return { ok: false, error: "Missing newElement" }
        var dyn = newEl(ET.DYNAMIC)
        dyn.text = cmd.text || "mf"
        var veloMap = {
            "pppp":10,"ppp":25,"pp":36,"p":49,"mp":64,"mf":80,
            "f":96,"ff":112,"fff":120,"ffff":126,
            "fp":96,"sfz":112,"sf":112,"fz":112,"rfz":112,
            "sfp":49,"sffz":126,"fpp":36
        }
        if (veloMap[cmd.text]) dyn.velocity = veloMap[cmd.text]
        cursor.staffIdx = staffIdx; cursor.voice = 0
        cursor.rewindToTick(tick)
        cursor.add(dyn)
        return { ok: true }
    }

    // =====================================================================
    //  ARTICULATIONS & FERMATA
    // =====================================================================

    case "addArticulation": {
        if (!newEl) return { ok: false, error: "Missing newElement" }
        var art = newEl(ET.ARTICULATION)
        if (cmd.symbol !== undefined) art.symbol = cmd.symbol
        if (cmd.direction !== undefined) art.direction = cmd.direction
        cursor.staffIdx = staffIdx; cursor.voice = voice
        cursor.rewindToTick(tick)
        cursor.add(art)
        return { ok: true }
    }

    case "addFermata": {
        if (!newEl) return { ok: false, error: "Missing newElement" }
        var ferm = newEl(ET.FERMATA)
        cursor.staffIdx = staffIdx; cursor.voice = voice
        cursor.rewindToTick(tick)
        cursor.add(ferm)
        return { ok: true }
    }

    // =====================================================================
    //  ARPEGGIO
    // =====================================================================

    case "addArpeggio": {
        if (!newEl) return { ok: false, error: "Missing newElement" }
        var arp = newEl(ET.ARPEGGIO)
        if (cmd.subtype !== undefined) arp.subtype = cmd.subtype
        cursor.staffIdx = staffIdx; cursor.voice = voice
        cursor.rewindToTick(tick)
        cursor.add(arp)
        return { ok: true }
    }

    // =====================================================================
    //  TEXT MARKINGS
    // =====================================================================

    case "addStaffText": {
        if (!newEl) return { ok: false, error: "Missing newElement" }
        var st = newEl(ET.STAFF_TEXT)
        st.text = cmd.text || ""
        if (cmd.fontSize) st.fontSize = cmd.fontSize
        if (cmd.fontFace) st.fontFace = cmd.fontFace
        if (cmd.placement !== undefined) st.placement = cmd.placement
        cursor.staffIdx = staffIdx; cursor.voice = 0
        cursor.rewindToTick(tick)
        cursor.add(st)
        return { ok: true }
    }

    case "addSystemText": {
        if (!newEl) return { ok: false, error: "Missing newElement" }
        var syst = newEl(ET.SYSTEM_TEXT)
        syst.text = cmd.text || ""
        cursor.staffIdx = 0; cursor.voice = 0
        cursor.rewindToTick(tick)
        cursor.add(syst)
        return { ok: true }
    }

    case "addRehearsalMark": {
        if (!newEl) return { ok: false, error: "Missing newElement" }
        var rm = newEl(ET.REHEARSAL_MARK)
        rm.text = cmd.text || ""
        cursor.staffIdx = staffIdx; cursor.voice = 0
        cursor.rewindToTick(tick)
        cursor.add(rm)
        return { ok: true }
    }

    case "addExpressionText": {
        if (!newEl) return { ok: false, error: "Missing newElement" }
        var expr = newEl(ET.STAFF_TEXT)
        expr.text = cmd.text || ""
        expr.placement = 1  // below staff
        expr.fontStyle = 1  // italic
        cursor.staffIdx = staffIdx; cursor.voice = 0
        cursor.rewindToTick(tick)
        cursor.add(expr)
        return { ok: true }
    }

    // =====================================================================
    //  LYRICS
    // =====================================================================

    case "addLyrics": {
        if (!newEl) return { ok: false, error: "Missing newElement" }
        var lyr = newEl(ET.LYRICS)
        lyr.text = cmd.text || ""
        if (cmd.verse !== undefined) lyr.verse = cmd.verse
        cursor.staffIdx = staffIdx; cursor.voice = voice
        cursor.rewindToTick(tick)
        cursor.add(lyr)
        return { ok: true }
    }

    // Write one syllable per note starting at tick
    case "writeLyrics": {
        if (!newEl) return { ok: false, error: "Missing newElement" }
        var syllables = cmd.syllables || []
        cursor.staffIdx = staffIdx; cursor.voice = voice
        cursor.rewindToTick(tick)
        for (var j = 0; j < syllables.length; j++) {
            if (cursor.element && syllables[j] !== "") {
                var lyr = newEl(ET.LYRICS)
                lyr.text = syllables[j]
                if (cmd.verse !== undefined) lyr.verse = cmd.verse
                cursor.add(lyr)
            }
            cursor.next()
        }
        return { ok: true }
    }

    // =====================================================================
    //  HARMONY / CHORD SYMBOLS
    // =====================================================================

    case "addHarmony": {
        // NOTE: chord-symbol insertion can crash MuseScore 4 from plugin API.
        // Return a safe error instead of risking a host crash.
        return {
            ok: false,
            error: "addHarmony is disabled: MuseScore 4 may crash when adding chord symbols from plugin API."
        }
    }

    // =====================================================================
    //  FINGERING
    // =====================================================================

    case "addFingering": {
        if (!newEl) return { ok: false, error: "Missing newElement" }
        var fing = newEl(ET.FINGERING)
        fing.text = cmd.text || ""
        cursor.staffIdx = staffIdx; cursor.voice = voice
        cursor.rewindToTick(tick)
        cursor.add(fing)
        return { ok: true }
    }

    // =====================================================================
    //  BREATH / CAESURA
    // =====================================================================

    case "addBreath": {
        if (!newEl) return { ok: false, error: "Missing newElement" }
        var breath = newEl(ET.BREATH)
        cursor.staffIdx = staffIdx; cursor.voice = 0
        cursor.rewindToTick(tick)
        cursor.add(breath)
        return { ok: true }
    }

    // =====================================================================
    //  TUPLETS
    // =====================================================================

    case "addTuplet": {
        if (!fracFn) return { ok: false, error: "Missing fraction" }
        var totalDur = durationFraction(cmd.totalDuration || "quarter", 0)
        cursor.staffIdx = staffIdx; cursor.voice = voice
        cursor.rewindToTick(tick)
        cursor.addTuplet(
            fracFn(cmd.actual || 3, cmd.normal || 2),
            fracFn(totalDur[0], totalDur[1])
        )
        return { ok: true }
    }

    // =====================================================================
    //  LAYOUT
    // =====================================================================

    case "addLayoutBreak": {
        if (!newEl) return { ok: false, error: "Missing newElement" }
        var lb = newEl(ET.LAYOUT_BREAK)
        // 0 = line break, 1 = page break, 2 = section break
        if (cmd.breakType !== undefined) lb.layoutBreakType = cmd.breakType
        cursor.staffIdx = 0; cursor.voice = 0
        cursor.rewindToTick(tick)
        cursor.add(lb)
        return { ok: true }
    }

    case "addSpacer": {
        if (!newEl) return { ok: false, error: "Missing newElement" }
        var sp = newEl(ET.SPACER)
        if (cmd.space !== undefined) sp.space = cmd.space
        cursor.staffIdx = staffIdx; cursor.voice = 0
        cursor.rewindToTick(tick)
        cursor.add(sp)
        return { ok: true }
    }

    // =====================================================================
    //  MEASURE PROPERTIES
    // =====================================================================

    case "modifyMeasure": {
        cursor.staffIdx = 0; cursor.voice = 0
        cursor.rewindToTick(tick)
        var measure = cursor.measure
        if (!measure) return { ok: false, error: "No measure at tick " + tick }
        if (cmd.repeatCount !== undefined) measure.repeatCount = cmd.repeatCount
        if (cmd.userStretch !== undefined) measure.userStretch = cmd.userStretch
        if (cmd.irregular !== undefined) measure.irregular = cmd.irregular
        return { ok: true }
    }

    default:
        return { ok: false, error: "Unknown op: " + cmd.op }
    }
}


// ─── Score Reading ──────────────────────────────────────────────────────────

function scoreInfo(score) {
    return {
        title: score.title, composer: score.composer,
        nstaves: score.nstaves, ntracks: score.ntracks,
        nmeasures: score.nmeasures, duration: score.duration,
        keysig: score.keysig, tpq: 480
    }
}

function readScore(score, elTypes) {
    var cursor = score.newCursor()
    var events = []
    for (var s = 0; s < score.nstaves; s++) {
        for (var v = 0; v < 4; v++) {
            cursor.staffIdx = s; cursor.voice = v
            cursor.rewind(0)
            while (cursor.segment) {
                var el = cursor.element
                if (el) {
                    var ev = {
                        tick: cursor.tick, staffIdx: s, voice: v,
                        durN: el.duration ? el.duration.numerator : 0,
                        durD: el.duration ? el.duration.denominator : 0
                    }
                    if (el.notes && el.notes.length > 0) {
                        ev.type = "chord"
                        ev.pitches = []
                        for (var n = 0; n < el.notes.length; n++)
                            ev.pitches.push(el.notes[n].pitch)
                    } else {
                        ev.type = "rest"
                    }
                    events.push(ev)
                }
                cursor.next()
            }
        }
    }
    return events
}
