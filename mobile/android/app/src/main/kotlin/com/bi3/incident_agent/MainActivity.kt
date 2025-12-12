package com.bi3.incident_agent

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.telephony.SmsManager
import android.telephony.PhoneStateListener
import android.telephony.TelephonyManager
import android.content.Context
import android.media.AudioManager  // NEW
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity: FlutterActivity() {
    private val CHANNEL = "com.bi3.incident_agent/telephony"
    private val PERMISSION_REQUEST_CODE = 1001
    
    private var telephonyManager: TelephonyManager? = null
    private var audioManager: AudioManager? = null  // NEW
    private var methodChannel: MethodChannel? = null
    private var phoneStateListener: PhoneStateListener? = null
    
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        
        telephonyManager = getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
        audioManager = getSystemService(Context.AUDIO_SERVICE) as AudioManager  // NEW
        
        methodChannel = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
        methodChannel?.setMethodCallHandler { call, result ->
            when (call.method) {
                "makeCall" -> {
                    val phoneNumber = call.argument<String>("phoneNumber")
                    if (phoneNumber != null) {
                        makeCall(phoneNumber, result)
                    } else {
                        result.error("INVALID_ARGUMENT", "Phone number is required", null)
                    }
                }
                "sendSMS" -> {
                    val phoneNumber = call.argument<String>("phoneNumber")
                    val message = call.argument<String>("message")
                    if (phoneNumber != null && message != null) {
                        sendSMS(phoneNumber, message, result)
                    } else {
                        result.error("INVALID_ARGUMENT", "Phone number and message are required", null)
                    }
                }
                "setAudioModeForCall" -> {  // NEW
                    setAudioModeForCall(result)
                }
                "restoreAudioMode" -> {  // NEW
                    restoreAudioMode(result)
                }
                "requestPermissions" -> {
                    requestPermissions(result)
                }
                "checkPermissions" -> {
                    val hasPermissions = checkPermissions()
                    result.success(hasPermissions)
                }
                else -> {
                    result.notImplemented()
                }
            }
        }
    }
    
    private fun makeCall(phoneNumber: String, result: MethodChannel.Result) {
        if (!checkCallPermission()) {
            result.error("PERMISSION_DENIED", "Call permission not granted", null)
            return
        }
        
        try {
            // Set audio mode for in-call communication
            setAudioModeForCall(null)
            
            // Create phone state listener to monitor call
            phoneStateListener = object : PhoneStateListener() {
                override fun onCallStateChanged(state: Int, incomingNumber: String?) {
                    when (state) {
                        TelephonyManager.CALL_STATE_RINGING -> {
                            methodChannel?.invokeMethod("onCallStateChanged", mapOf(
                                "state" to "RINGING",
                                "phoneNumber" to incomingNumber
                            ))
                        }
                        TelephonyManager.CALL_STATE_OFFHOOK -> {
                            // Call answered/active - ensure audio is routed correctly
                            setAudioModeForCall(null)
                            methodChannel?.invokeMethod("onCallStateChanged", mapOf(
                                "state" to "OFFHOOK",
                                "phoneNumber" to phoneNumber
                            ))
                        }
                        TelephonyManager.CALL_STATE_IDLE -> {
                            // Call ended - restore normal audio mode
                            restoreAudioMode(null)
                            methodChannel?.invokeMethod("onCallStateChanged", mapOf(
                                "state" to "IDLE",
                                "phoneNumber" to phoneNumber
                            ))
                            telephonyManager?.listen(this, PhoneStateListener.LISTEN_NONE)
                        }
                    }
                }
            }
            
            // Start listening to call state
            telephonyManager?.listen(phoneStateListener, PhoneStateListener.LISTEN_CALL_STATE)
            
            // Make the call
            val intent = Intent(Intent.ACTION_CALL)
            intent.data = Uri.parse("tel:$phoneNumber")
            startActivity(intent)
            
            result.success(true)
            
        } catch (e: Exception) {
            result.error("CALL_FAILED", e.message, null)
        }
    }
    
    // NEW: Set audio mode for in-call TTS with loudspeaker
    private fun setAudioModeForCall(result: MethodChannel.Result?) {
        try {
            // Set audio mode to IN_CALL (not IN_COMMUNICATION)
            // This allows us to control the audio routing
            audioManager?.mode = AudioManager.MODE_IN_CALL
            
            // Enable speakerphone at MAXIMUM volume
            audioManager?.isSpeakerphoneOn = true
            
            // Set media volume to maximum for TTS playback
            val maxVolume = audioManager?.getStreamMaxVolume(AudioManager.STREAM_MUSIC) ?: 15
            audioManager?.setStreamVolume(
                AudioManager.STREAM_MUSIC,
                maxVolume,
                0  // No flags
            )
            
            // Also set voice call volume to maximum
            val maxVoiceVolume = audioManager?.getStreamMaxVolume(AudioManager.STREAM_VOICE_CALL) ?: 15
            audioManager?.setStreamVolume(
                AudioManager.STREAM_VOICE_CALL,
                maxVoiceVolume,
                0
            )
            
            // Set notification volume to max (TTS might use this)
            val maxNotifVolume = audioManager?.getStreamMaxVolume(AudioManager.STREAM_NOTIFICATION) ?: 15
            audioManager?.setStreamVolume(
                AudioManager.STREAM_NOTIFICATION,
                maxNotifVolume,
                0
            )
            
            result?.success(true)
        } catch (e: Exception) {
            result?.error("AUDIO_ERROR", e.message, null)
        }
    }
    
    // NEW: Restore normal audio mode
    private fun restoreAudioMode(result: MethodChannel.Result?) {
        try {
            audioManager?.mode = AudioManager.MODE_NORMAL
            audioManager?.isSpeakerphoneOn = false
            result?.success(true)
        } catch (e: Exception) {
            result?.error("AUDIO_ERROR", e.message, null)
        }
    }
    
    private fun sendSMS(phoneNumber: String, message: String, result: MethodChannel.Result) {
        if (!checkSMSPermission()) {
            result.error("PERMISSION_DENIED", "SMS permission not granted", null)
            return
        }
        
        try {
            val smsManager = SmsManager.getDefault()
            
            // Split message if it's too long
            val parts = smsManager.divideMessage(message)
            
            if (parts.size == 1) {
                smsManager.sendTextMessage(phoneNumber, null, message, null, null)
            } else {
                smsManager.sendMultipartTextMessage(phoneNumber, null, parts, null, null)
            }
            
            methodChannel?.invokeMethod("onSMSSent", mapOf(
                "phoneNumber" to phoneNumber,
                "success" to true
            ))
            
            result.success(true)
        } catch (e: Exception) {
            methodChannel?.invokeMethod("onSMSSent", mapOf(
                "phoneNumber" to phoneNumber,
                "success" to false,
                "error" to e.message
            ))
            result.error("SMS_FAILED", e.message, null)
        }
    }
    
    private fun requestPermissions(result: MethodChannel.Result) {
        val permissions = arrayOf(
            Manifest.permission.CALL_PHONE,
            Manifest.permission.READ_PHONE_STATE,
            Manifest.permission.READ_CALL_LOG,
            Manifest.permission.SEND_SMS,
            Manifest.permission.READ_SMS,
            Manifest.permission.MODIFY_AUDIO_SETTINGS  // NEW: For audio routing
        )
        
        ActivityCompat.requestPermissions(this, permissions, PERMISSION_REQUEST_CODE)
        result.success(null)
    }
    
    private fun checkPermissions(): Boolean {
        return checkCallPermission() && checkSMSPermission()
    }
    
    private fun checkCallPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.CALL_PHONE
        ) == PackageManager.PERMISSION_GRANTED &&
        ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.READ_PHONE_STATE
        ) == PackageManager.PERMISSION_GRANTED
    }
    
    private fun checkSMSPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            this,
            Manifest.permission.SEND_SMS
        ) == PackageManager.PERMISSION_GRANTED
    }
    
    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        
        if (requestCode == PERMISSION_REQUEST_CODE) {
            val allGranted = grantResults.all { it == PackageManager.PERMISSION_GRANTED }
            methodChannel?.invokeMethod("onPermissionsResult", allGranted)
        }
    }
    
    override fun onDestroy() {
        super.onDestroy()
        // Clean up
        phoneStateListener?.let {
            telephonyManager?.listen(it, PhoneStateListener.LISTEN_NONE)
        }
        restoreAudioMode(null)
    }
}
