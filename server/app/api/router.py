# Love Journal - a private journal + blog + real-time interaction platform for couples.
# Copyright (C) 2026 Love Journal Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from fastapi import APIRouter

from app.api.v1.albums import router as albums_router
from app.api.v1.articles import router as articles_router
from app.api.v1.audit_logs import router as audit_logs_router
from app.api.v1.auth import router as auth_router
from app.api.v1.capsules import router as capsules_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.events import router as events_router
from app.api.v1.export import router as export_router
from app.api.v1.health import router as health_router
from app.api.v1.messages import router as messages_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.push import router as push_router
from app.api.v1.privacy import router as privacy_router
from app.api.v1.search import router as search_router
from app.api.v1.security import router as security_router
from app.api.v1.settings import router as settings_router
from app.api.v1.timeline import router as timeline_router
from app.api.v1.uploads import router as uploads_router
from app.api.v1.checkins import router as checkins_router
from app.api.v1.cottage_chat import router as cottage_chat_router
from app.api.v1.cottage_chat_keys import router as cottage_chat_keys_router
from app.api.v1.cottage_chat_ws import router as cottage_chat_ws_router
from app.api.v1.cottage_coupons import router as cottage_coupons_router
from app.api.v1.cottage_footprints import router as cottage_footprints_router
from app.api.v1.cottage_ledger import router as cottage_ledger_router
from app.api.v1.cottage_listen import router as cottage_listen_router
from app.api.v1.cottage_listen_ws import router as cottage_listen_ws_router
from app.api.v1.cottage_mood import router as cottage_mood_router
from app.api.v1.cottage_period import router as cottage_period_router
from app.api.v1.cottage_vault import router as cottage_vault_router
from app.api.v1.cottage_plans import router as cottage_plans_router
from app.api.v1.cottage_questions import router as cottage_questions_router
from app.api.v1.cottage_reminders import router as cottage_reminders_router
from app.api.v1.cottage_reports import router as cottage_reports_router
from app.api.v1.cottage_watch import router as cottage_watch_router
from app.api.v1.cottage_watch_ws import router as cottage_watch_ws_router
from app.api.v1.cottage_games import router as cottage_games_router
from app.api.v1.cottage_games_ws import router as cottage_games_ws_router
from app.api.v1.cottage_canvas_ws import router as cottage_canvas_ws_router
from app.api.v1.cottage_canvas_artworks import router as cottage_canvas_artworks_router
from app.api.v1.cottage_draw import router as cottage_draw_router
from app.api.v1.cottage_draw_ws import router as cottage_draw_ws_router
from app.api.v1.recycle_bin import router as recycle_bin_router
from app.api.v1.wishes import router as wishes_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router, prefix="/v1")
api_router.include_router(timeline_router, prefix="/v1")
api_router.include_router(checkins_router, prefix="/v1")
api_router.include_router(cottage_listen_router, prefix="/v1")
api_router.include_router(cottage_listen_ws_router, prefix="/v1")
api_router.include_router(cottage_watch_router, prefix="/v1")
api_router.include_router(cottage_watch_ws_router, prefix="/v1")
api_router.include_router(cottage_chat_router, prefix="/v1")
api_router.include_router(cottage_chat_keys_router, prefix="/v1")
api_router.include_router(cottage_chat_ws_router, prefix="/v1")
api_router.include_router(cottage_mood_router, prefix="/v1")
api_router.include_router(cottage_games_router, prefix="/v1")
api_router.include_router(cottage_games_ws_router, prefix="/v1")
api_router.include_router(cottage_canvas_ws_router, prefix="/v1")
api_router.include_router(cottage_canvas_artworks_router, prefix="/v1")
api_router.include_router(cottage_draw_router, prefix="/v1")
api_router.include_router(cottage_draw_ws_router, prefix="/v1")
api_router.include_router(cottage_questions_router, prefix="/v1")
api_router.include_router(cottage_plans_router, prefix="/v1")
api_router.include_router(cottage_reminders_router, prefix="/v1")
api_router.include_router(cottage_reports_router, prefix="/v1")
api_router.include_router(cottage_coupons_router, prefix="/v1")
api_router.include_router(cottage_ledger_router, prefix="/v1")
api_router.include_router(cottage_period_router, prefix="/v1")
api_router.include_router(cottage_vault_router, prefix="/v1")
api_router.include_router(cottage_footprints_router, prefix="/v1")
api_router.include_router(wishes_router, prefix="/v1")
api_router.include_router(events_router, prefix="/v1")
api_router.include_router(articles_router, prefix="/v1")
api_router.include_router(audit_logs_router, prefix="/v1")
api_router.include_router(albums_router, prefix="/v1")
api_router.include_router(messages_router, prefix="/v1")
api_router.include_router(notifications_router, prefix="/v1")
api_router.include_router(push_router, prefix="/v1")
api_router.include_router(privacy_router, prefix="/v1")
api_router.include_router(search_router, prefix="/v1")
api_router.include_router(settings_router, prefix="/v1")
api_router.include_router(uploads_router, prefix="/v1")
api_router.include_router(export_router, prefix="/v1")
api_router.include_router(dashboard_router, prefix="/v1")
api_router.include_router(capsules_router, prefix="/v1")
api_router.include_router(security_router, prefix="/v1")
api_router.include_router(recycle_bin_router, prefix="/v1")
