/*
 * Love Journal - a private journal + blog + real-time interaction platform for couples.
 * Copyright (C) 2026 Love Journal Contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published
 * by the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

package com.lovejournal.app

import android.app.Application
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkRequest
import androidx.hilt.work.HiltWorkerFactory
import androidx.work.Configuration
import coil.ImageLoader
import coil.ImageLoaderFactory
import com.lovejournal.app.data.prefs.SessionManager
import com.lovejournal.app.data.local.LoveDatabase
import com.lovejournal.app.data.remote.AuthCookieJar
import com.lovejournal.app.data.remote.SessionEventBus
import com.lovejournal.app.data.repository.PushRepository
import com.lovejournal.app.push.NotificationChannels
import com.lovejournal.app.sync.SyncScheduler
import dagger.hilt.EntryPoint
import dagger.hilt.InstallIn
import dagger.hilt.android.EntryPointAccessors
import dagger.hilt.android.HiltAndroidApp
import dagger.hilt.components.SingletonComponent
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import okhttp3.OkHttpClient
import javax.inject.Inject
import javax.inject.Named

@HiltAndroidApp
class LoveJournalApp : Application(), Configuration.Provider, ImageLoaderFactory {

    @Inject
    lateinit var workerFactory: HiltWorkerFactory

    @Inject
    lateinit var sessionEventBus: SessionEventBus

    @Inject
    lateinit var cookieJar: AuthCookieJar

    @Inject
    lateinit var sessionManager: SessionManager

    @Inject
    lateinit var pushRepository: PushRepository

    @Inject
    lateinit var database: LoveDatabase

    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    /** Exposes the cookie-aware (ws) OkHttp client to non-injectable call sites. */
    @EntryPoint
    @InstallIn(SingletonComponent::class)
    interface MediaClientEntryPoint {
        @Named("ws")
        fun mediaClient(): OkHttpClient
    }

    override fun onCreate() {
        super.onCreate()
        NotificationChannels.register(this)
        SyncScheduler.schedulePeriodicSync(this)
        observeSessionExpiry()
        observePushTokenRegistration()
        observeConnectivity()
    }

    /**
     * When any request gets a 401, drop the local session so the app returns to
     * the login screen instead of looping on failed calls.
     */
    private fun observeSessionExpiry() {
        appScope.launch {
            sessionEventBus.sessionExpired.collect {
                cookieJar.clear()
                sessionManager.clear()
                runCatching {
                    database.messageDao().clear()
                    database.moodDao().clear()
                    database.eventDao().clear()
                    // Keep sync_queue: each row is scoped by server + uid and
                    // can safely resume only for that same account.
                }
                // A remotely revoked session is still a logout. Invalidate the
                // local device token without calling the authenticated delete
                // endpoint (which would return another 401 and recurse). Do it
                // after local logout so a slow Firebase call cannot hold the UI
                // in an authenticated state.
                runCatching { pushRepository.deleteLocalFcmToken().getOrThrow() }
            }
        }
    }

    private fun observePushTokenRegistration() {
        appScope.launch {
            sessionManager.sessionFlow
                .map { it.loggedIn }
                .distinctUntilChanged()
                .collect { loggedIn ->
                    if (loggedIn) runCatching { pushRepository.registerCurrentFcmToken().getOrThrow() }
                }
        }
    }

    /**
     * React to network up/down transitions: as soon as a validated
     * internet-capable network appears, fire an immediate one-shot
     * SyncWorker so queued mutations drain without waiting for the next
     * 15-minute periodic tick. The reverse (network loss) is a no-op —
     * the periodic worker simply retries on the next eligible window.
     */
    private fun observeConnectivity() {
        val cm = getSystemService(ConnectivityManager::class.java) ?: return
        val request = NetworkRequest.Builder()
            .addCapability(android.net.NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .addCapability(android.net.NetworkCapabilities.NET_CAPABILITY_VALIDATED)
            .build()
        try {
            cm.registerNetworkCallback(request, object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) {
                    SyncScheduler.requestSyncNow(this@LoveJournalApp)
                }
            })
        } catch (_: Exception) {
            // Some devices / profiles disallow callback registration; the
            // periodic tick still runs as a fallback.
        }
    }

    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder()
            .setWorkerFactory(workerFactory)
            .build()

    override fun newImageLoader(): ImageLoader {
        val mediaClient = EntryPointAccessors
            .fromApplication(this, MediaClientEntryPoint::class.java)
            .mediaClient()
        return ImageLoader.Builder(this)
            .okHttpClient(mediaClient)
            .build()
    }
}
