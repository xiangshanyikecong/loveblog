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

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import ensure_partner, get_current_user
from app.db.session import get_db
from app.models.site_setting import SiteSetting
from app.models.user import User
from app.schemas.site_setting import SiteSettingResponse, SiteSettingUpdateRequest
from app.services.audit import write_audit_log
from app.services.upload_references import sync_site_setting_upload_references


router = APIRouter(prefix="/settings", tags=["settings"])

_SIMPLE_FIELDS = (
    "site_name",
    "love_start_date",
    "uploads_root",
    "articles_path",
    "albums_path",
    "avatar_path",
    "timeline_path",
    "videos_path",
    "allow_registration",
    "partner_a_avatar",
    "partner_b_avatar",
    # Media policy
    "max_image_kb",
    "thumb_width",
    "compress_quality",
    "strip_exif",
    "allowed_image_types",
)


def _to_response(item: SiteSetting) -> SiteSettingResponse:
    return SiteSettingResponse(
        site_name=item.site_name,
        love_start_date=item.love_start_date,
        uploads_root=item.uploads_root,
        articles_path=item.articles_path,
        albums_path=item.albums_path,
        avatar_path=item.avatar_path,
        timeline_path=item.timeline_path,
        videos_path=item.videos_path,
        allow_registration=item.allow_registration,
        partner_a_avatar=item.partner_a_avatar,
        partner_b_avatar=item.partner_b_avatar,
        max_image_kb=item.max_image_kb,
        thumb_width=item.thumb_width,
        compress_quality=item.compress_quality,
        strip_exif=item.strip_exif,
        allowed_image_types=item.allowed_image_types,
    )


def _get_or_create_setting(db: Session) -> SiteSetting:
    setting = db.query(SiteSetting).filter(SiteSetting.id == 1).first()
    if setting is not None:
        return setting
    setting = SiteSetting(id=1)
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


@router.get("", response_model=SiteSettingResponse)
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SiteSettingResponse:
    ensure_partner(current_user)
    setting = _get_or_create_setting(db)
    return _to_response(setting)


@router.put("", response_model=SiteSettingResponse)
def update_settings(
    payload: SiteSettingUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SiteSettingResponse:
    ensure_partner(current_user)
    setting = _get_or_create_setting(db)
    update_data = payload.model_dump(exclude_unset=True)
    changed_fields: list[str] = []
    for field in _SIMPLE_FIELDS:
        if field in update_data:
            if getattr(setting, field) != update_data[field]:
                changed_fields.append(field)
            setattr(setting, field, update_data[field])
    db.commit()
    db.refresh(setting)
    sync_site_setting_upload_references(db, setting)
    db.commit()
    response = _to_response(setting)
    if changed_fields:
        write_audit_log(
            db,
            action="settings.update",
            actor=current_user,
            resource_type="site_settings",
            resource_id="1",
            resource_name=setting.site_name,
            detail={"changed_fields": changed_fields},
        )
    return response
