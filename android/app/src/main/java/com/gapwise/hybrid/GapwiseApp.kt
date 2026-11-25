package com.gapwise.hybrid

import android.app.Application
import com.google.firebase.FirebaseApp

class GapwiseApp : Application() {
    override fun onCreate() {
        super.onCreate()
        if (FirebaseApp.getApps(this).isEmpty()) {
            runCatching { FirebaseApp.initializeApp(this) }
        }
        if (FirebaseApp.getApps(this).isNotEmpty()) {
            AppCheckInitializer.install(this)
        }
    }
}
