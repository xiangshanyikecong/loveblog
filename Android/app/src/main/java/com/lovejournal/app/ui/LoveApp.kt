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

package com.lovejournal.app.ui

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.Cottage
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.PhotoLibrary
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Article
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.NavigationBarDefaults
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.lovejournal.app.ui.albums.AlbumsScreen
import com.lovejournal.app.ui.admin.AdminToolsScreen
import com.lovejournal.app.ui.articles.ArticlesScreen
import com.lovejournal.app.ui.auth.AuthViewModel
import com.lovejournal.app.ui.auth.LoginScreen
import com.lovejournal.app.ui.cottage.CottageRoute
import com.lovejournal.app.ui.cottage.CottageScreen
import com.lovejournal.app.ui.cottage.chat.ChatScreen
import com.lovejournal.app.ui.cottage.coupons.CouponScreen
import com.lovejournal.app.ui.cottage.footprints.FootprintScreen
import com.lovejournal.app.ui.cottage.games.canvas.CanvasScreen
import com.lovejournal.app.ui.cottage.games.canvas.CanvasGalleryScreen
import com.lovejournal.app.ui.cottage.games.canvas.CanvasArtworkPlayerScreen
import com.lovejournal.app.ui.cottage.games.draw.DrawScreen
import com.lovejournal.app.ui.cottage.games.GameScreen
import com.lovejournal.app.ui.cottage.games.GamesLobbyScreen
import com.lovejournal.app.ui.cottage.ledger.LedgerScreen
import com.lovejournal.app.ui.cottage.listen.ListenScreen
import com.lovejournal.app.ui.cottage.period.PeriodScreen
import com.lovejournal.app.ui.cottage.plans.PlanScreen
import com.lovejournal.app.ui.cottage.questions.DailyQuestionScreen
import com.lovejournal.app.ui.cottage.reminders.ReminderScreen
import com.lovejournal.app.ui.cottage.reports.ReportScreen
import com.lovejournal.app.ui.cottage.watch.WatchScreen
import com.lovejournal.app.ui.cottage.vault.VaultScreen
import com.lovejournal.app.ui.cottage.wishlist.WishlistScreen
import com.lovejournal.app.ui.capsules.CapsuleScreen
import com.lovejournal.app.ui.checkins.CheckinScreen
import com.lovejournal.app.ui.dashboard.DashboardScreen
import com.lovejournal.app.ui.licenses.LicensesScreen
import com.lovejournal.app.ui.notifications.NotificationScreen
import com.lovejournal.app.ui.recyclebin.RecycleBinScreen
import com.lovejournal.app.ui.search.SearchScreen
import com.lovejournal.app.ui.security.SecurityScreen
import com.lovejournal.app.ui.settings.SettingsScreen
import com.lovejournal.app.ui.timeline.TimelineScreen
import com.lovejournal.app.ui.events.EventsScreen
import com.lovejournal.app.ui.messages.MessagesScreen
import com.lovejournal.app.ui.mood.MoodScreen

private enum class Tab(val route: String, val label: String, val icon: ImageVector) {
    Dashboard("dashboard", "首页", Icons.Filled.Favorite),
    Events("events", "纪念日", Icons.Filled.CalendarMonth),
    Articles("articles", "文章", Icons.AutoMirrored.Filled.Article),
    Albums("albums", "相册", Icons.Filled.PhotoLibrary),
    Cottage(CottageRoute.HUB, "小屋", Icons.Filled.Cottage),
    Messages("messages", "互动", Icons.AutoMirrored.Filled.Chat),
}

/** 主端二级页路由（从顶栏入口进入，非底部 Tab）。 */
private object MainRoute {
    const val SEARCH = "search"
    const val NOTIFICATIONS = "notifications"
    const val TIMELINE = "timeline"
    const val CAPSULES = "capsules"
    const val SETTINGS = "settings"
    const val LICENSES = "licenses"
    const val SECURITY = "security"
    const val RECYCLE_BIN = "recycle-bin"
    const val ADMIN_TOOLS = "admin-tools"
}

private val SECONDARY_ROUTES = setOf(
    MainRoute.SEARCH,
    MainRoute.NOTIFICATIONS,
    MainRoute.TIMELINE,
    MainRoute.CAPSULES,
    MainRoute.SETTINGS,
    MainRoute.LICENSES,
    MainRoute.SECURITY,
    MainRoute.RECYCLE_BIN,
    MainRoute.ADMIN_TOOLS,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LoveApp(authViewModel: AuthViewModel = hiltViewModel()) {
    val session by authViewModel.session.collectAsStateWithLifecycle()

    if (!session.loggedIn) {
        LoginScreen()
        return
    }

    val navController = rememberNavController()
    val backStack by navController.currentBackStackEntryAsState()
    val currentDestination = backStack?.destination
    val currentRoute = currentDestination?.route
    val title = when (currentRoute) {
        CottageRoute.HUB -> "我们的小屋"
        CottageRoute.CHAT -> "悄悄话"
        CottageRoute.MOOD -> "心情打卡"
        CottageRoute.WISHLIST -> "心愿单"
        CottageRoute.QUESTIONS -> "每日一问"
        CottageRoute.GAMES -> "一起玩"
        CottageRoute.WATCH -> "一起看"
        CottageRoute.LISTEN -> "一起听"
        CottageRoute.COUPONS -> "甜蜜兑换券"
        CottageRoute.REMINDERS -> "小屋提醒"
        CottageRoute.LEDGER -> "情侣账本"
        CottageRoute.REPORTS -> "恋爱月报"
        CottageRoute.FOOTPRINTS -> "足迹地图"
        CottageRoute.PERIOD -> "生理期关怀"
        CottageRoute.PLANS -> "约会计划"
        CottageRoute.CHECKINS -> "报备签到"
        CottageRoute.CANVAS -> "协作画板"
        CottageRoute.CANVAS_GALLERY -> "作品集"
        CottageRoute.CANVAS_ARTWORK -> "作品回放"
        MainRoute.SEARCH -> "搜索"
        MainRoute.NOTIFICATIONS -> "通知中心"
        MainRoute.TIMELINE -> "时间线"
        MainRoute.CAPSULES -> "时间胶囊"
        MainRoute.SETTINGS -> "设置"
        MainRoute.LICENSES -> "开源许可证"
        MainRoute.SECURITY -> "账号安全"
        MainRoute.RECYCLE_BIN -> "回收站"
        Tab.Messages.route -> "留言板"
        "cottage/games/{game}" -> "对局中"
        else -> session.nickname ?: "恋爱记"
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(title) },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.surface.copy(alpha = 0.94f)),
                navigationIcon = {
                    if (currentRoute in SECONDARY_ROUTES) {
                        IconButton(onClick = { navController.navigateUp() }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                        }
                    }
                },
                actions = {
                    if (currentRoute !in SECONDARY_ROUTES) {
                        IconButton(onClick = { navController.navigate(MainRoute.SEARCH) { launchSingleTop = true } }) {
                            Icon(Icons.Filled.Search, contentDescription = "搜索")
                        }
                        IconButton(onClick = { navController.navigate(MainRoute.NOTIFICATIONS) { launchSingleTop = true } }) {
                            Icon(Icons.Filled.Notifications, contentDescription = "通知中心")
                        }
                        var menuOpen by remember { mutableStateOf(false) }
                        IconButton(onClick = { menuOpen = true }) {
                            Icon(Icons.Filled.MoreVert, contentDescription = "更多")
                        }
                        DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                            DropdownMenuItem(
                                text = { Text("时间线") },
                                onClick = {
                                    menuOpen = false
                                    navController.navigate(MainRoute.TIMELINE) { launchSingleTop = true }
                                },
                            )
                            DropdownMenuItem(
                                text = { Text("时间胶囊") },
                                onClick = {
                                    menuOpen = false
                                    navController.navigate(MainRoute.CAPSULES) { launchSingleTop = true }
                                },
                            )
                            DropdownMenuItem(
                                text = { Text("设置") },
                                onClick = {
                                    menuOpen = false
                                    navController.navigate(MainRoute.SETTINGS) { launchSingleTop = true }
                                },
                            )
                        }
                    }
                },
            )
        },
        bottomBar = {
            Surface(
                color = MaterialTheme.colorScheme.surface,
                tonalElevation = 8.dp,
            ) {
                NavigationBar(
                    containerColor = androidx.compose.ui.graphics.Color.Transparent,
                    tonalElevation = 0.dp,
                ) {
                    Tab.entries.forEach { tab ->
                        val selected = if (tab == Tab.Cottage) {
                            // Stay highlighted while on the hub or any cottage sub-screen.
                            currentRoute?.startsWith("cottage") == true
                        } else {
                            currentDestination?.hierarchy?.any { it.route == tab.route } == true
                        }
                        NavigationBarItem(
                            selected = selected,
                            onClick = {
                                navController.navigate(tab.route) {
                                    popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            icon = { Icon(tab.icon, contentDescription = tab.label) },
                            label = { Text(tab.label, style = MaterialTheme.typography.labelSmall) },
                            alwaysShowLabel = true,
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = MaterialTheme.colorScheme.onPrimaryContainer,
                                selectedTextColor = MaterialTheme.colorScheme.primary,
                                indicatorColor = MaterialTheme.colorScheme.primaryContainer,
                                unselectedIconColor = MaterialTheme.colorScheme.onSurfaceVariant,
                                unselectedTextColor = MaterialTheme.colorScheme.onSurfaceVariant,
                            ),
                        )
                    }
                }
            }
        },
    ) { padding ->
        NavHost(
            navController = navController,
            startDestination = Tab.Dashboard.route,
            modifier = Modifier.padding(padding),
        ) {
            composable(Tab.Dashboard.route) { DashboardScreen() }
            composable(Tab.Events.route) { EventsScreen() }
            composable(Tab.Articles.route) { ArticlesScreen() }
            composable(Tab.Albums.route) { AlbumsScreen() }
            composable(Tab.Messages.route) { MessagesScreen() }
            composable(CottageRoute.HUB) {
                CottageScreen(onOpen = { route -> navController.navigate(route) })
            }
            composable(CottageRoute.CHAT) { ChatScreen() }
            composable(CottageRoute.MOOD) { MoodScreen() }
            composable(CottageRoute.WISHLIST) { WishlistScreen() }
            composable(CottageRoute.QUESTIONS) { DailyQuestionScreen() }
            composable(CottageRoute.WATCH) { WatchScreen() }
            composable(CottageRoute.LISTEN) { ListenScreen() }
            composable(CottageRoute.COUPONS) { CouponScreen() }
            composable(CottageRoute.REMINDERS) { ReminderScreen() }
            composable(CottageRoute.LEDGER) { LedgerScreen() }
            composable(CottageRoute.REPORTS) { ReportScreen() }
            composable(CottageRoute.FOOTPRINTS) { FootprintScreen() }
            composable(CottageRoute.PERIOD) { PeriodScreen() }
            composable(CottageRoute.VAULT) { VaultScreen() }
            composable(CottageRoute.PLANS) { PlanScreen() }
            composable(CottageRoute.CHECKINS) { CheckinScreen() }
            composable(MainRoute.SEARCH) { SearchScreen() }
            composable(MainRoute.NOTIFICATIONS) { NotificationScreen() }
            composable(MainRoute.TIMELINE) { TimelineScreen() }
            composable(MainRoute.CAPSULES) { CapsuleScreen() }
            composable(MainRoute.SETTINGS) {
                SettingsScreen(
                    onLogout = { authViewModel.logout() },
                    onOpenSecurity = { navController.navigate(MainRoute.SECURITY) { launchSingleTop = true } },
                    onOpenRecycleBin = { navController.navigate(MainRoute.RECYCLE_BIN) { launchSingleTop = true } },
                    onOpenAdminTools = { navController.navigate(MainRoute.ADMIN_TOOLS) { launchSingleTop = true } },
                    onOpenLicenses = { navController.navigate(MainRoute.LICENSES) { launchSingleTop = true } },
                )
            }
            composable(MainRoute.LICENSES) { LicensesScreen() }
            composable(MainRoute.SECURITY) { SecurityScreen() }
            composable(MainRoute.RECYCLE_BIN) { RecycleBinScreen() }
            composable(MainRoute.ADMIN_TOOLS) { AdminToolsScreen() }
            composable(CottageRoute.CANVAS) {
                CanvasScreen(
                    onOpenGallery = { navController.navigate(CottageRoute.CANVAS_GALLERY) },
                )
            }
            composable(CottageRoute.CANVAS_GALLERY) {
                CanvasGalleryScreen(
                    onBack = { navController.navigateUp() },
                    onOpenArtwork = { caid -> navController.navigate("${CottageRoute.CANVAS_GALLERY}/$caid") },
                )
            }
            composable("${CottageRoute.CANVAS_GALLERY}/{caid}") { entry ->
                val caid = entry.arguments?.getString("caid") ?: ""
                CanvasArtworkPlayerScreen(
                    caid = caid,
                    onBack = { navController.navigateUp() },
                )
            }
            composable(CottageRoute.GAMES) {
                GamesLobbyScreen(onOpen = { key -> navController.navigate("${CottageRoute.GAMES}/$key") })
            }
            composable("${CottageRoute.GAMES}/{game}") { entry ->
                val game = entry.arguments?.getString("game") ?: "gomoku"
                when (game) {
                    "draw" -> DrawScreen()
                    "canvas" -> CanvasScreen()
                    else -> GameScreen(gameKey = game)
                }
            }
        }
    }
}
