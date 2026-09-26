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

package com.lovejournal.app.data.remote

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 地址归一化规则单测。覆盖「直连 :8000 后端」与「反代 /api 域名」两种部署形态
 * 的地址推导——这是登录页最核心的纯逻辑，出错会导致整站不可达。
 */
class ServerAddressTest {

    // ------------------------------------------------------------------ normalize

    @Test
    fun `bare domain uses proxy path and default port`() {
        assertEquals("https://demo.com/api/v1", ServerAddress.normalize("demo.com", null, false))
    }

    @Test
    fun `explicit api path is preserved`() {
        assertEquals(
            "https://demo.com/api/v1",
            ServerAddress.normalize("https://demo.com/api", null, false),
        )
        assertEquals(
            "https://demo.com/api/v1",
            ServerAddress.normalize("https://demo.com/api/v1", null, false),
        )
    }

    @Test
    fun `domain without path appends api v1`() {
        assertEquals(
            "https://demo.com/api/v1",
            ServerAddress.normalize("https://demo.com", null, false),
        )
    }

    @Test
    fun `domain with custom path appends v1`() {
        assertEquals(
            "https://demo.com/love/v1",
            ServerAddress.normalize("https://demo.com/love", null, false),
        )
    }

    @Test
    fun `ip literal defaults to backend port 8000`() {
        assertEquals(
            "http://192.168.1.5:8000/v1",
            ServerAddress.normalize("http://192.168.1.5", null, false),
        )
        // 裸主机名按原实现补 https 协议
        assertEquals(
            "https://192.168.1.5:8000/v1",
            ServerAddress.normalize("192.168.1.5", null, false),
        )
    }

    @Test
    fun `emulator keeps explicit port and skips proxy path`() {
        assertEquals(
            "http://10.0.2.2:8000/v1",
            ServerAddress.normalize("http://10.0.2.2:8000", null, false),
        )
    }

    @Test
    fun `localhost defaults to backend port 8000`() {
        assertEquals(
            "https://localhost:8000/v1",
            ServerAddress.normalize("https://localhost", null, false),
        )
    }

    @Test
    fun `explicit non-default port is kept`() {
        assertEquals(
            "https://demo.com:8443/v1",
            ServerAddress.normalize("https://demo.com:8443/v1", null, false),
        )
    }

    @Test
    fun `query and fragment are stripped`() {
        assertEquals(
            "https://demo.com/api/v1",
            ServerAddress.normalize("https://demo.com/?from=qr#top", null, false),
        )
    }

    @Test
    fun `trailing slash is stripped and case-insensitive v1 recognized`() {
        // 已带 v1（大小写不敏感）的路径原样保留大小写
        assertEquals(
            "http://192.168.1.5:8000/V1",
            ServerAddress.normalize("http://192.168.1.5:8000/V1/", null, false),
        )
    }

    @Test
    fun `empty input falls back to emulator default only on emulator`() {
        assertEquals("http://10.0.2.2:8000/v1", ServerAddress.normalize("", "http://10.0.2.2:8000/v1", true))
        assertEquals("", ServerAddress.normalize("", "http://10.0.2.2:8000/v1", false))
    }

    @Test
    fun `unparseable input is returned as-is`() {
        val weird = "https://de mo.com"
        assertEquals(weird, ServerAddress.normalize(weird, null, false))
    }

    // ---------------------------------------------------------------- stripping

    @Test
    fun `stripApiVersion removes v1 and api v1`() {
        // 原实现仅去掉 "/v1"，/api 前缀保留
        assertEquals("https://demo.com/api", ServerAddress.stripApiVersion("https://demo.com/api/v1"))
        assertEquals("http://192.168.1.5:8000", ServerAddress.stripApiVersion("http://192.168.1.5:8000/v1"))
        assertEquals("https://demo.com", ServerAddress.stripApiVersion("https://demo.com"))
    }

    @Test
    fun `stripMediaApiPrefix removes the full api v1 prefix`() {
        assertEquals("https://demo.com", ServerAddress.stripMediaApiPrefix("https://demo.com/api/v1"))
        assertEquals("http://192.168.1.5:8000", ServerAddress.stripMediaApiPrefix("http://192.168.1.5:8000/v1"))
    }

    // ----------------------------------------------------------- validateAddressInput

    @Test
    fun `blank input reports missing address`() {
        assertEquals("请输入服务器地址", ServerAddress.validateAddressInput("   ", false))
    }

    @Test
    fun `missing scheme reports incomplete address`() {
        assertEquals("请填写完整的 https:// 服务器地址", ServerAddress.validateAddressInput("demo.com", false))
    }

    @Test
    fun `valid https address passes`() {
        assertNull(ServerAddress.validateAddressInput("https://demo.com", false))
    }

    @Test
    fun `cleartext allowed only for local development hosts when enabled`() {
        assertNull(ServerAddress.validateAddressInput("http://192.168.1.5:8000", true))
        assertNull(ServerAddress.validateAddressInput("http://10.0.2.2:8000", true))
        // 公网域名走 HTTP 始终拒绝，即便调试版放开了明文限制
        assertNotNull(ServerAddress.validateAddressInput("http://demo.com", true))
        // 正式版（allowCleartext=false）一切明文都拒绝
        assertNotNull(ServerAddress.validateAddressInput("http://192.168.1.5:8000", false))
    }

    @Test
    fun `garbage host reports format error`() {
        val error = ServerAddress.validateAddressInput("https://de mo.com", false)
        assertNotNull(error)
        assertTrue(error!!.contains("格式"))
    }
}
