package com.airscreen.networking

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import com.airscreen.config.TrustStore

/** Announces this receiver as _airscreen._tcp via mDNS. Contains no secrets: discovery is not authentication. */
class DiscoveryAdvertiser(context: Context, private val port: Int, private val trust: TrustStore) {
    private val nsd = context.applicationContext.getSystemService(Context.NSD_SERVICE) as NsdManager
    private var listener: NsdManager.RegistrationListener? = null

    fun register() {
        if (listener != null) return
        val info = NsdServiceInfo().apply {
            serviceName = trust.name
            serviceType = "_airscreen._tcp."
            port = this@DiscoveryAdvertiser.port
            setAttribute("id", trust.receiverId)
            setAttribute("name", trust.name)
            setAttribute("v", Protocol.VERSION.toString())
        }
        val l = object : NsdManager.RegistrationListener {
            override fun onServiceRegistered(serviceInfo: NsdServiceInfo) = Unit
            override fun onRegistrationFailed(serviceInfo: NsdServiceInfo, errorCode: Int) {
                listener = null // manual IP entry still works
            }
            override fun onServiceUnregistered(serviceInfo: NsdServiceInfo) = Unit
            override fun onUnregistrationFailed(serviceInfo: NsdServiceInfo, errorCode: Int) = Unit
        }
        listener = l
        try {
            nsd.registerService(info, NsdManager.PROTOCOL_DNS_SD, l)
        } catch (_: Exception) {
            listener = null
        }
    }

    fun unregister() {
        val l = listener ?: return
        listener = null
        try {
            nsd.unregisterService(l)
        } catch (_: Exception) {
        }
    }
}
