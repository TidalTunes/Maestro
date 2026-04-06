import QtQuick 2.9
import MuseScore 3.0
import FileIO 3.0

import "score_operations.js" as Ops
import "bridge_actions.js" as BridgeActions

MuseScore {
    menuPath: "Plugins.Maestro.Maestro Plugin"
    description: "Maestro Plugin for direct score editing from Python scripts."
    version: "1.0"
    pluginType: "dialog"
    requiresScore: false

    width: 640
    height: 300

    property string protocolVersion: "maestro.bridge.v1"
    property string bridgeDir: pathProbe.homePath() + "/.maestro-musescore-bridge"
    property string requestPath: bridgeDir + "/request.json"
    property string responsePath: bridgeDir + "/response.json"

    property string statusMsg: "Idle (waiting for request.json)"
    property string lastRequestId: ""
    property int handledCount: 0
    property bool running: true
    property bool busy: false

    FileIO {
        id: pathProbe
        source: ""
    }

    FileIO {
        id: requestFile
        source: requestPath
        onError: {
            statusMsg = "Request file error: " + msg
        }
    }

    FileIO {
        id: responseFile
        source: responsePath
        onError: {
            statusMsg = "Response file error: " + msg
        }
    }

    Timer {
        id: bridgePoller
        interval: 10
        repeat: true
        running: true
        onTriggered: pollBridge()
    }

    function elementTypes() {
        return {
            TIMESIG: Element.TIMESIG,
            KEYSIG: Element.KEYSIG,
            CLEF: Element.CLEF,
            TEMPO_TEXT: Element.TEMPO_TEXT,
            DYNAMIC: Element.DYNAMIC,
            ARTICULATION: Element.ARTICULATION,
            FERMATA: Element.FERMATA,
            ARPEGGIO: Element.ARPEGGIO,
            STAFF_TEXT: Element.STAFF_TEXT,
            SYSTEM_TEXT: Element.SYSTEM_TEXT,
            REHEARSAL_MARK: Element.REHEARSAL_MARK,
            LYRICS: Element.LYRICS,
            HARMONY: Element.HARMONY,
            FINGERING: Element.FINGERING,
            BREATH: Element.BREATH,
            LAYOUT_BREAK: Element.LAYOUT_BREAK,
            SPACER: Element.SPACER
        }
    }

    function isArray(value) {
        return Object.prototype.toString.call(value) === "[object Array]"
    }

    function allOk(results) {
        for (var i = 0; i < results.length; i++) {
            if (!(results[i] && results[i].ok === true))
                return false
        }
        return true
    }

    function nowIso() {
        return new Date().toISOString()
    }

    function buildBaseResponse(requestId) {
        return {
            protocol: protocolVersion,
            request_id: requestId || "",
            ok: false,
            result: {},
            error: ""
        }
    }

    function requireScore() {
        if (!curScore)
            throw new Error("No score is open. Open a score in MuseScore before sending this operation.")
    }

    function exportCurrentScore(requestId) {
        if (typeof writeScore !== "function")
            throw new Error("MuseScore plugin host does not expose writeScore().")

        var stem = "score-" + (requestId || "latest")
        var basePath = bridgeDir + "/" + stem

        function cleanupCandidate(path) {
            pathProbe.source = path
            if (pathProbe.exists())
                pathProbe.remove()
        }

        function detectExportedPath(base, ext) {
            var candidates = [
                base + "." + ext,
                base,
                base + "." + ext + "." + ext
            ]
            for (var i = 0; i < candidates.length; i++) {
                pathProbe.source = candidates[i]
                if (pathProbe.exists())
                    return candidates[i]
            }
            return ""
        }

        cleanupCandidate(basePath)
        cleanupCandidate(basePath + ".musicxml")
        cleanupCandidate(basePath + ".musicxml.musicxml")
        cleanupCandidate(basePath + ".xml")
        cleanupCandidate(basePath + ".xml.xml")

        var wrotePrimary = false
        var primaryError = ""
        try {
            wrotePrimary = !!writeScore(curScore, basePath, "musicxml")
        } catch (err) {
            primaryError = String(err)
        }

        var primaryOutputPath = detectExportedPath(basePath, "musicxml")
        if (wrotePrimary || primaryOutputPath !== "") {
            if (primaryOutputPath === "")
                throw new Error("writeScore reported success but no MusicXML file was created.")
            return {
                path: primaryOutputPath,
                format: "musicxml"
            }
        }

        var wroteFallback = false
        var fallbackError = ""
        try {
            wroteFallback = !!writeScore(curScore, basePath, "xml")
        } catch (fallbackErr) {
            fallbackError = String(fallbackErr)
        }

        var fallbackOutputPath = detectExportedPath(basePath, "xml")
        if (wroteFallback || fallbackOutputPath !== "") {
            if (fallbackOutputPath === "")
                throw new Error("writeScore fallback reported success but no XML file was created.")
            return {
                path: fallbackOutputPath,
                format: "xml"
            }
        }

        var details = []
        if (primaryError)
            details.push("musicxml export error: " + primaryError)
        if (fallbackError)
            details.push("xml export error: " + fallbackError)
        throw new Error(
            "Failed to export the open score to MusicXML."
            + (details.length ? " " + details.join(" | ") : "")
        )
    }

    function handleRequestObject(request) {
        var response = buildBaseResponse(request.request_id)
        response.received_at = nowIso()

        if (request.protocol && request.protocol !== protocolVersion)
            throw new Error("Unsupported protocol. Expected " + protocolVersion + ", got " + request.protocol)

        var operation = request.operation || "apply_actions"

        if (operation === "ping") {
            response.ok = true
            response.result = {
                message: "pong",
                has_score: !!curScore,
                handled_count: handledCount,
                plugin_version: version,
                protocol: protocolVersion
            }
            return response
        }

        if (operation === "list_actions") {
            response.ok = true
            response.result = {
                actions: BridgeActions.listActionSpecs(),
                note: "Use operation=apply_actions with one or more action objects."
            }
            return response
        }

        if (operation === "score_info") {
            requireScore()
            response.ok = true
            response.result = Ops.scoreInfo(curScore)
            return response
        }

        if (operation === "read_score") {
            requireScore()
            response.ok = true
            response.result = {
                events: Ops.readScore(curScore, elementTypes())
            }
            return response
        }

        if (operation === "export_musicxml") {
            requireScore()
            response.ok = true
            response.result = exportCurrentScore(request.request_id)
            return response
        }

        if (operation === "apply_actions") {
            requireScore()
            if (!isArray(request.actions))
                throw new Error("actions must be an array")

            var commands = []
            for (var i = 0; i < request.actions.length; i++)
                commands.push(BridgeActions.toCommand(request.actions[i]))

            var commandResults = Ops.executeCommands(
                curScore,
                commands,
                newElement,
                fraction,
                removeElement,
                elementTypes()
            )

            var okAll = allOk(commandResults)
            var failOnPartial = request.fail_on_partial !== false

            response.ok = okAll || !failOnPartial
            response.result = {
                command_count: commands.length,
                all_ok: okAll,
                results: commandResults
            }
            if (!response.ok)
                response.error = "One or more actions failed"

            return response
        }

        if (operation === "apply_commands") {
            requireScore()
            if (!isArray(request.commands))
                throw new Error("commands must be an array")

            var directResults = Ops.executeCommands(
                curScore,
                request.commands,
                newElement,
                fraction,
                removeElement,
                elementTypes()
            )
            var directOk = allOk(directResults)
            var directFailOnPartial = request.fail_on_partial !== false

            response.ok = directOk || !directFailOnPartial
            response.result = {
                command_count: request.commands.length,
                all_ok: directOk,
                results: directResults
            }
            if (!response.ok)
                response.error = "One or more commands failed"
            return response
        }

        throw new Error("Unknown operation: " + operation)
    }

    function handleRequestRaw(raw) {
        var parsed = null
        var response = null

        try {
            parsed = JSON.parse(raw)
        } catch (e) {
            response = buildBaseResponse("")
            response.error = "Invalid JSON request: " + String(e)
            response.received_at = nowIso()
            return response
        }

        try {
            response = handleRequestObject(parsed)
        } catch (err) {
            response = buildBaseResponse(parsed.request_id)
            response.error = String(err)
            response.received_at = nowIso()
        }

        return response
    }

    function pollBridge() {
        if (!running || busy)
            return
        if (!requestFile.exists())
            return

        busy = true

        var raw = requestFile.read()
        requestFile.remove()

        var response = handleRequestRaw(raw)
        response.responded_at = nowIso()

        responseFile.write(JSON.stringify(response, null, 2))

        handledCount += 1
        lastRequestId = response.request_id || ""

        if (response.ok)
            statusMsg = "Handled request " + (lastRequestId || "(no id)")
        else
            statusMsg = "Request failed: " + response.error

        busy = false
    }

    Rectangle {
        x: 0
        y: 0
        width: 640
        height: 300
        color: "#111827"

        Text {
            x: 20
            y: 16
            text: "Maestro Plugin"
            color: "#f8fafc"
            font.pixelSize: 22
            font.bold: true
        }

        Text {
            x: 20
            y: 48
            text: "Protocol: " + protocolVersion
            color: "#cbd5e1"
            font.pixelSize: 12
        }

        Text {
            x: 20
            y: 68
            width: 600
            wrapMode: Text.Wrap
            text: "Bridge directory: " + bridgeDir
            color: "#94a3b8"
            font.pixelSize: 11
        }

        Rectangle {
            x: 20
            y: 104
            width: 600
            height: 74
            radius: 6
            color: "#1f2937"

            Text {
                x: 10
                y: 8
                width: 580
                wrapMode: Text.Wrap
                text: statusMsg
                color: "#e2e8f0"
                font.pixelSize: 12
            }

            Text {
                x: 10
                y: 44
                text: "Handled: " + handledCount + "   Last request id: " + (lastRequestId || "none")
                color: "#93c5fd"
                font.pixelSize: 11
            }
        }

        Rectangle {
            x: 20
            y: 194
            width: 180
            height: 34
            radius: 5
            color: toggleArea.pressed ? "#7f1d1d" : "#991b1b"

            Text {
                anchors.centerIn: parent
                text: running ? "Pause Bridge" : "Resume Bridge"
                color: "#ffffff"
                font.pixelSize: 12
                font.bold: true
            }

            MouseArea {
                id: toggleArea
                anchors.fill: parent
                onClicked: {
                    running = !running
                    statusMsg = running ? "Bridge resumed" : "Bridge paused"
                }
            }
        }

        Rectangle {
            x: 214
            y: 194
            width: 180
            height: 34
            radius: 5
            color: clearArea.pressed ? "#14532d" : "#166534"

            Text {
                anchors.centerIn: parent
                text: "Clear response.json"
                color: "#ffffff"
                font.pixelSize: 12
                font.bold: true
            }

            MouseArea {
                id: clearArea
                anchors.fill: parent
                onClicked: {
                    if (responseFile.exists()) {
                        responseFile.remove()
                        statusMsg = "Deleted response.json"
                    } else {
                        statusMsg = "No response.json to delete"
                    }
                }
            }
        }

        Text {
            x: 20
            y: 246
            width: 600
            wrapMode: Text.Wrap
            text: "Keep this plugin dialog open while running Python scripts. The client writes request.json and waits for response.json."
            color: "#94a3b8"
            font.pixelSize: 11
        }
    }

    onRun: {
        statusMsg = "Bridge active. Waiting for request.json"
    }
}
