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
    }

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
        return OkHttpClient.Builder()
            .cookieJar(cookieJar)
            .addInterceptor(hostSelectionInterceptor)
            .addInterceptor(authStatusInterceptor)
            .addInterceptor(logging)
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            // Photo uploads can be large on slow links; the default 10s write
            // timeout truncated them, so allow a longer body-write window.
            .writeTimeout(60, TimeUnit.SECONDS)
            .build()
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
