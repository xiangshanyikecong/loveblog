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

package com.lovejournal.app.di

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import com.lovejournal.app.BuildConfig
import com.lovejournal.app.data.remote.AuthCookieJar
import com.lovejournal.app.data.remote.AuthStatusInterceptor
import com.lovejournal.app.data.remote.HostSelectionInterceptor
import com.lovejournal.app.data.remote.api.LoveApiService
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.CipherSuite
import okhttp3.ConnectionSpec
import okhttp3.TlsVersion
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit
import javax.inject.Named
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    @OptIn(kotlinx.serialization.ExperimentalSerializationApi::class)
    fun provideJson(): Json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
        explicitNulls = false
        // 序列化默认值字段：服务端多个请求模型把 confirm/iterations 等声明为必填，
        // 若省略默认值字段会直接触发 422（如 vault setup 的 iterations、
        // revoke-sessions 的 confirm），因此必须显式发送。
        encodeDefaults = true
    }

    /**
     * TLS connection policy for release builds: TLS 1.2 / 1.3 only, and only
     * modern cipher suites (forward secrecy with AEAD). The debug build keeps
     * the system default to allow local HTTP (10.0.2.2) without bumping into a
     * MODERN_TLS-only spec.
     *
     * Static certificate pinning is intentionally NOT used: this app is
     * self-hosted and the server host is user-configurable, so a pre-baked pin
     * would either lock everyone into one certificate or require the operator
     * to rebuild the app on every cert rotation. The network_security_config
     * already rejects cleartext and user-installed CAs on release; forbidding
     * legacy TLS closes the remaining downgrade surface without that downside.
     */
    private fun modernTlsSpec(): ConnectionSpec = ConnectionSpec.Builder(ConnectionSpec.MODERN_TLS)
        .tlsVersions(TlsVersion.TLS_1_2, TlsVersion.TLS_1_3)
        .cipherSuites(
            // AEAD + forward secrecy only — drop CBC / static-RSA suites that
            // OkHttp's MODERN_TLS preset would otherwise still accept.
            CipherSuite.TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256,
            CipherSuite.TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384,
            CipherSuite.TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256,
            CipherSuite.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384,
            CipherSuite.TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305_SHA256,
            CipherSuite.TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305_SHA256,
            CipherSuite.TLS_AES_128_GCM_SHA256,
            CipherSuite.TLS_AES_256_GCM_SHA384,
            CipherSuite.TLS_CHACHA20_POLY1305_SHA256,
        )
        .build()

    @Provides
    @Singleton
    fun provideOkHttp(
        cookieJar: AuthCookieJar,
        hostSelectionInterceptor: HostSelectionInterceptor,
        authStatusInterceptor: AuthStatusInterceptor,
    ): OkHttpClient {
        val logging = HttpLoggingInterceptor().apply {
            level = if (BuildConfig.DEBUG) {
                HttpLoggingInterceptor.Level.BASIC
            } else {
                HttpLoggingInterceptor.Level.NONE
            }
        }
        val builder = OkHttpClient.Builder()
            .cookieJar(cookieJar)
            .addInterceptor(hostSelectionInterceptor)
            .addInterceptor(authStatusInterceptor)
            .addInterceptor(logging)
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            // Photo uploads can be large on slow links; the default 10s write
            // timeout truncated them, so allow a longer body-write window.
            .writeTimeout(60, TimeUnit.SECONDS)
        // Debug builds allow the system default spec (needed for local HTTP to
        // 10.0.2.2); release restricts to modern TLS only — and since
        // network_security_config forbids cleartext on release, no CLEARTEXT
        // spec is added here.
        if (!BuildConfig.DEBUG) {
            builder.connectionSpecs(listOf(modernTlsSpec()))
        }
        return builder.build()
    }

    /**
     * Dedicated client for cottage WebSockets: shares the auth cookie jar but
     * deliberately omits [HostSelectionInterceptor] (the WS URL is built
     * absolutely, so no rewrite is needed) and uses no read timeout since the
     * socket is long-lived.
     */
    @Provides
    @Singleton
    @Named("ws")
    fun provideWebSocketOkHttp(cookieJar: AuthCookieJar): OkHttpClient =
        OkHttpClient.Builder()
            .cookieJar(cookieJar)
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(0, TimeUnit.SECONDS)
            .build()

    @Provides
    @Singleton
    fun provideRetrofit(client: OkHttpClient, json: Json): Retrofit =
        Retrofit.Builder()
            .baseUrl(BuildConfig.API_BASE_URL)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()

    @Provides
    @Singleton
    fun provideApiService(retrofit: Retrofit): LoveApiService =
        retrofit.create(LoveApiService::class.java)
}
