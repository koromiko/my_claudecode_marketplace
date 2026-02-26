#!/bin/bash
# Detects whether the user is in a video meeting.
# Exit 0 = in meeting (suppress notifications), Exit 1 = not in meeting.
#
# Detection strategy:
# 1. Zoom active call — pgrep -x CptHost (~5ms). CptHost only exists during an active Zoom meeting.
# 2. Microphone in use — CoreAudio API via inline Swift (~240ms). Catches Google Meet, Teams, etc.

# Fast path: Zoom active call
if pgrep -x CptHost &>/dev/null; then
  exit 0
fi

# Slow path: check if any audio input device has its mic active via CoreAudio
swift -e '
import CoreAudio
import Foundation

var propertyAddress = AudioObjectPropertyAddress(
  mSelector: kAudioHardwarePropertyDevices,
  mScope: kAudioObjectPropertyScopeGlobal,
  mElement: kAudioObjectPropertyElementMain
)

var dataSize: UInt32 = 0
var status = AudioObjectGetPropertyDataSize(
  AudioObjectID(kAudioObjectSystemObject),
  &propertyAddress,
  0, nil,
  &dataSize
)
guard status == noErr else { exit(1) }

let deviceCount = Int(dataSize) / MemoryLayout<AudioDeviceID>.size
var devices = [AudioDeviceID](repeating: 0, count: deviceCount)
status = AudioObjectGetPropertyData(
  AudioObjectID(kAudioObjectSystemObject),
  &propertyAddress,
  0, nil,
  &dataSize,
  &devices
)
guard status == noErr else { exit(1) }

for device in devices {
  // Check if this device has input streams (i.e., is a mic)
  var inputAddress = AudioObjectPropertyAddress(
    mSelector: kAudioDevicePropertyStreams,
    mScope: kAudioObjectPropertyScopeInput,
    mElement: kAudioObjectPropertyElementMain
  )
  var inputSize: UInt32 = 0
  let inputStatus = AudioObjectGetPropertyDataSize(device, &inputAddress, 0, nil, &inputSize)
  if inputStatus != noErr || inputSize == 0 { continue }

  // Check if the device is running (mic in use)
  var runningAddress = AudioObjectPropertyAddress(
    mSelector: kAudioDevicePropertyDeviceIsRunningSomewhere,
    mScope: kAudioObjectPropertyScopeGlobal,
    mElement: kAudioObjectPropertyElementMain
  )
  var isRunning: UInt32 = 0
  var runningSize = UInt32(MemoryLayout<UInt32>.size)
  let runningStatus = AudioObjectGetPropertyData(device, &runningAddress, 0, nil, &runningSize, &isRunning)
  if runningStatus == noErr && isRunning != 0 {
    exit(0)  // Mic is active — in a meeting
  }
}

exit(1)  // No active mic found
' 2>/dev/null || true

# If Swift failed or exited non-zero, default to "not in meeting"
exit 1
