import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15


ApplicationWindow {
    id: win; visible: true; width: 1150; height: 720
    title: "IPCSync Debugger"; color: "#f4f4f4"

    // This is the main layout for the entire window
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 15; spacing: 12

        // Top control bar
        RowLayout {
            spacing: 12
            Label { text: "Processes:"; font.pixelSize: 14 }
            SpinBox {
                id: procSpin
                from: 2; to: 20; value: 6
                // Disable controls while running
                enabled: !backend.running
            }
            Label { text: "IPC:"; font.pixelSize: 14 }
            ComboBox {
                id: ipcCombo
                model: ["Pipe","MsgQueue","SharedMem"]
                // Disable controls while running
                enabled: !backend.running
                // Notify backend so it can update button state
                onCurrentIndexChanged: backend.channelTypeChanged()
            }

            // Start/Stop Button
            Button {
                text: backend.running ? "Stop" : "Start"
                onClicked: backend.running ? backend.stop() : backend.start(procSpin.value, ipcCombo.currentIndex)
                background: Rectangle { color: backend.running ? "#e74c3c" : "#27ae60"; radius: 6 }
                contentItem: Text { text: parent.text; color: "white"; horizontalAlignment: Text.AlignHCenter; font.bold: true }
            }
            // Export Log Button
            Button {
                text: "Export Log"
                onClicked: backend.exportLog()
                background: Rectangle { color: "#9b59b6"; radius: 6 }
                contentItem: Text { text: parent.text; color: "white"; horizontalAlignment: Text.AlignHCenter }
            }
            // Force Deadlock Button
            Button {
                id: deadlockButton
                text: backend.deadlockActive ? "Deadlock: ON" : "Force Deadlock"
                onClicked: backend.toggleDeadlock()
                // Only enable *before* start and *only* for SharedMem (index 2)
                enabled: !backend.running && ipcCombo.currentIndex === 2
                background: Rectangle {
                    color: backend.deadlockActive ? "#c0392b" : (deadlockButton.enabled ? "#e67e22" : "#95a5a6")
                    radius: 6
                }
                contentItem: Text { text: parent.text; color: "white"; font.bold: backend.deadlockActive; horizontalAlignment: Text.AlignHCenter }
            }

            Item { Layout.fillWidth: true } // Spacer

            // Stats Display
            Column {
                spacing: 2
                Text { text: backend.throughput; font.pixelSize: 13; color: "#2c3e50"; font.bold: true }
                Text { text: backend.latency;    font.pixelSize: 13; color: "#2c3e50"; font.bold: true }
            }
            Text { text: backend.status; font.italic: true; color: "#2c3e50" }
        }

        // Main visualization area for processes
        Rectangle {
            Layout.fillWidth: true; Layout.fillHeight: true
            color: "#ecf0f1"; radius: 10; clip: true

            // Repeater to create the process boxes
            Repeater {
                model: backend.running ? procSpin.value : 0
                delegate: Rectangle {
                    width: 90; height: 90
                    
                    // --- UPDATED COLOR LOGIC ---
                    // If this process index is in the frozen list, turn red.
                    // Otherwise, use the alternating colors.
                    color: backend.frozenProcesses.includes(index) ? "#c0392b" : (index % 2 === 0 ? "#27ae60" : "#3498db")
                    // --- END UPDATED LOGIC ---
                    
                    radius: 12
                    // Basic grid layout logic
                    x: (index % 6)*115 + 40
                    y: Math.floor(index/6)*135 + 40
                    border.color: "#2c3e50"; border.width: 2

                    Column {
                        anchors.centerIn: parent; spacing: -4
                        Text { text: "P"+index; color: "white"; font.bold: true; font.pixelSize: 18 }
                        Text {
                            // This text is for the *automatic* deadlock, not the demo
                            text: backend.deadlockActive && index >= 2 ? "DEADLOCK" : ""
                            color: "#ff3333"; font.bold: true; font.pixelSize: 10
                            visible: text !== ""
                        }
                    }
                }
            }
            


            // Repeater for the animated data flow arrows
            Repeater { 
                id: arrows; model: []
                delegate: Rectangle {
                    width: 8; height: 8; color: "#e74c3c"; radius: 4
                    x: modelData.sx; y: modelData.sy
                    // Animate position from start (sx, sy) to end (ex, ey)
                    PropertyAnimation on x { to: modelData.ex; duration: 700; easing.type: Easing.OutQuad }
                    PropertyAnimation on y { to: modelData.ey; duration: 700; easing.type: Easing.OutQuad }
                    // Timer to remove the arrow after animation
                    Timer { interval: 750; onTriggered: arrows.model = arrows.model.filter((_,i)=>i!==index) }
                }
            }
            
            // Connection to the backend to receive data flow events
            Connections {
                target: backend
                function onDataFlow(src,dst) {
                    if (src===-1 || dst===-1) return; // Ignore invalid
                    // Calculate start and end coordinates based on process index
                    var sx = (src%6)*115+85, sy = Math.floor(src/6)*135+85;
                    var ex = (dst%6)*115+85, ey = Math.floor(dst/6)*135+85;
                    // Add a new arrow animation to the model
                    arrows.model = arrows.model.concat([{sx:sx,sy:sy,ex:ex,ey:ey}]);
                }
            }
        }

        // Alert bar at the bottom (for automatic deadlock detection)
        Rectangle {
            Layout.fillWidth: true; height: 60
            color: "#e74c3c"; radius: 10
            visible: backend.alert !== "" // Only show if there is an alert
            border.color: "#c0392b"; border.width: 3
            RowLayout {
                anchors.centerIn: parent; spacing: 15
                Text { text: "WARNING"; color: "white"; font.pixelSize: 16; font.bold: true }
                Text { text: backend.alert; color: "white"; font.pixelSize: 18; font.bold: true }
            }
            // Blinking animation for attention
            SequentialAnimation on opacity {
                loops: Animation.Infinite; running: parent.visible
                PropertyAnimation { to: 0.7; duration: 500 }
                PropertyAnimation { to: 1.0; duration: 500 }
            }
        }

        // Log/Timeline view
        GroupBox {
            title: "Timeline"
            Layout.fillWidth: true; Layout.fillHeight: true
            ScrollView {
                anchors.fill: parent
                TextArea {
                    id: timelineArea; readOnly: true
                    text: backend.timeline // Bound to the backend's timeline property
                    font.family: "Consolas"; font.pixelSize: 13; color: "#2c3e50"
                    selectByMouse: true
                    background: Rectangle { color: "white"; radius: 6 }
                    
                    // Connection to auto-scroll to the bottom when text is added
                    Connections {
                        target: backend
                        function onTimelineChanged() {
                            // Only auto-scroll if the user isn't actively scrolled up
                            if (timelineArea.ScrollBar.vertical.position === 1.0 || !timelineArea.ScrollBar.vertical.active) {
                                timelineArea.cursorPosition = timelineArea.length
                                var sv = timelineArea.parent
                                sv.contentItem.contentY = Math.max(0, sv.contentItem.contentHeight - sv.height)
                            }
                        }
                    }
                }
            }
        }
    }
}
