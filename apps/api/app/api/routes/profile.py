import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.media import (
    AVATAR_KEY_PREFIX,
    avatar_storage_key_for,
    upload_source_hash,
)
from app.core.rate_limit import Quota, rate_limit
from app.core.storage import StorageError, get_driver
from app.models.user import User
from app.schemas.media import UploadTicket, UploadTicketRequest
from app.schemas.profile import (
    AvatarConfirm,
    BadgePublic,
    BadgesPublic,
    DailyTaskPublic,
    DailyTasksPublic,
    FramePublic,
    LearningStats,
    ProgressionPublic,
    UserProfilePublic,
    UserProfileUpdate,
)
from app.services import progression_config, ruby_daily
from app.services.badges import evaluate, mark_seen, record_new
from app.services.daily_tasks import grant_rewards, tasks_for
from app.services.profile import ensure_profile, profile_public
from app.services.profile_stats import gather_stats
from app.services.progression import daily_cap, progression_of

router = APIRouter(tags=["profile"])


@router.get("/profile", response_model=UserProfilePublic)
def read_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfilePublic:
    """Hồ sơ của CHÍNH người đang đăng nhập.

    Không có biến thể nhận id: hồ sơ ở đây là dữ liệu riêng — mục tiêu điểm, ngày
    thi, thời gian học mỗi ngày — chứ không phải trang cá nhân công khai. Một
    endpoint `/profile/{user_id}` sẽ phải trả lời câu hỏi "ai được xem của ai",
    và câu hỏi đó chưa có lý do tồn tại.
    """
    return profile_public(ensure_profile(db, current_user))


@router.patch("/profile", response_model=UserProfilePublic)
def update_profile(
    body: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfilePublic:
    """Cập nhật một phần hồ sơ.

    `exclude_unset=True` là điểm mấu chốt, không phải chi tiết: nó giữ được khác
    biệt giữa "không gửi trường này" và "gửi null để xoá trường này". Nếu gộp
    bằng `giá_trị or giá_trị_cũ` thì thao tác xoá ngày thi sẽ im lặng không làm
    gì cả, và người dùng chỉ phát hiện ra khi tải lại trang.
    """
    changes = body.model_dump(exclude_unset=True)
    profile = ensure_profile(db, current_user)

    for field, value in changes.items():
        # `timezone` và `locale` là NOT NULL. Gửi null cho chúng là yêu cầu vô
        # nghĩa chứ không phải yêu cầu xoá, nên bỏ qua thay vì để database ném
        # IntegrityError thành 500.
        if value is None and field in {"timezone", "locale"}:
            continue
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return profile_public(profile)


@router.get("/profile/stats", response_model=LearningStats)
def read_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LearningStats:
    """Thống kê học tập, tính lại mỗi lần đọc.

    Tách khỏi `GET /profile` chứ không gộp vào: hồ sơ là vài cột đọc thẳng, còn
    phần này quét bảng lượt ôn và lượt dictation. Gộp lại thì mỗi lần sửa tên
    hiển thị cũng phải trả giá cho toàn bộ phép đếm, và `SessionProvider` — vốn
    gọi `/auth/me` ở mọi lần tải trang — sẽ kéo theo chúng ở khắp mọi nơi.
    """
    profile = ensure_profile(db, current_user)
    return gather_stats(db, current_user.id, profile.timezone)


# --- avatar -----------------------------------------------------------------

# Hạn mức riêng và chặt hơn của khu nội dung: một người chỉ có MỘT avatar, nên
# nhu cầu thật là vài lần mỗi phiên. Rộng hơn thế chỉ mở cửa cho việc dùng tài
# khoản Cloudinary của ta làm nơi chứa file.
AVATAR_QUOTA = Quota(limit=10, window_seconds=60 * 10)


@router.post(
    "/profile/avatar/ticket",
    response_model=UploadTicket,
    dependencies=[Depends(rate_limit("avatar-ticket", AVATAR_QUOTA))],
)
def avatar_ticket(
    body: UploadTicketRequest,
    current_user: User = Depends(get_current_user),
) -> UploadTicket:
    """Vé upload avatar — mọi học viên đều xin được.

    Khác với ảnh nội dung, đường này KHÔNG đòi vai trò editor: đây là media của
    chính người dùng. Đổi lại, khoá nằm dưới tiền tố `avatar/` riêng, nên một
    lệnh dọn nhắm vào ảnh nội dung không thể chạm nhầm vào đây (ADR-006 §2.1).
    """
    storage_key = avatar_storage_key_for(upload_source_hash(str(uuid.uuid4())), ext=body.ext)
    ticket = get_driver("image").ticket(storage_key)
    return UploadTicket.of(ticket)


@router.post("/profile/avatar", response_model=UserProfilePublic)
def avatar_confirm(
    body: AvatarConfirm,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfilePublic:
    """Gắn ảnh vừa tải lên vào hồ sơ.

    Vẫn hỏi lại nhà cung cấp (§2.3): không có bước đó thì đây là đường ghi một
    chuỗi tuỳ ý vào `avatar_storage_key`, và giao diện sẽ hiện ảnh vỡ cho tới
    khi có người để ý.

    Khoá phải nằm dưới `avatar/`. Thiếu kiểm tra này thì một người có thể trỏ
    avatar của mình vào một ảnh nội dung, và lệnh dọn ảnh mồ côi sau này sẽ xoá
    mất thứ đang được dùng.
    """
    if not body.storage_key.startswith(f"{AVATAR_KEY_PREFIX}/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Khoá không thuộc vùng avatar"
        )
    try:
        get_driver("image").verify(body.storage_key)
    except StorageError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chưa thấy file trên kho lưu trữ: {error}",
        ) from None

    profile = ensure_profile(db, current_user)
    profile.avatar_storage_key = body.storage_key
    db.commit()
    db.refresh(profile)
    return profile_public(profile)


@router.delete("/profile/avatar", response_model=UserProfilePublic)
def avatar_remove(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfilePublic:
    """Gỡ avatar, rơi về ảnh chữ cái đầu.

    KHÔNG xoá file khỏi kho ngay tại đây. Xoá đồng bộ nghĩa là một request của
    người dùng phải chờ một dịch vụ bên ngoài trả lời, và nếu nó lỗi thì hồ sơ
    vẫn giữ ảnh cũ trong khi người dùng đã thấy thông báo thành công. File mồ
    côi để lệnh đối chiếu dọn — đó là việc nó sinh ra để làm (§10.4).
    """
    profile = ensure_profile(db, current_user)
    profile.avatar_storage_key = None
    db.commit()
    db.refresh(profile)
    return profile_public(profile)


def _frame_public(code: str | None, db: Session) -> FramePublic | None:
    """Bậc khung kèm cách vẽ. `None` khi level chưa tới bậc nào."""
    if code is None:
        return None
    row = next((t for t in progression_config.frame_tiers(db) if t.code == code), None)
    if row is None:
        return None
    return FramePublic(
        code=row.code,
        label=row.label,
        min_level=row.min_level,
        tone=row.tone,  # type: ignore[arg-type]
        ring=row.ring,
        image_url=(
            get_driver("image").public_url(row.image_storage_key) if row.image_storage_key else None
        ),
    )


@router.get("/profile/progression", response_model=ProgressionPublic)
def read_progression(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProgressionPublic:
    """Level, XP và bậc khung avatar.

    Nằm dưới `/profile` chứ không phải một router riêng: đây là thứ thuộc về hồ
    sơ của chính người đang đăng nhập, và nó dùng đúng `timezone` mà `/profile/stats`
    dùng để tính chuỗi ngày. Hai định nghĩa "hôm nay" khác nhau trong cùng một
    trang là chỗ hai con số nói hai điều về cùng một ngày.
    """
    profile = ensure_profile(db, current_user)
    # Quản trị viên đeo sẵn bậc khung cao nhất. Thuần trang trí và cố ý chỉ dừng
    # ở đó: level, XP và huy hiệu vẫn là số thật của chính họ.
    progress, frame, today = progression_of(
        db, current_user.id, profile.timezone, top_frame=current_user.role == "admin"
    )
    # `progression_of` có thể vừa nâng mốc nước cao trên hồ sơ. Commit ở đây chứ
    # không ở đó: dịch vụ không được tự quyết định ranh giới giao dịch của một
    # request, cùng luật với `award`.
    db.commit()
    return ProgressionPublic(
        xp_total=progress.xp_total,
        level=progress.level,
        xp_into_level=progress.xp_into_level,
        xp_for_next=progress.xp_for_next,
        frame=_frame_public(frame, db),
        xp_today=today,
        daily_cap=daily_cap(db),
    )


@router.get("/daily-tasks", response_model=DailyTasksPublic)
def read_daily_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DailyTasksPublic:
    """Ba việc hôm nay, và trao XP cho việc vừa xong.

    Đường dẫn gạch nối ở gốc `/api/v1/daily-tasks`, không lồng dưới `/profile`:
    đây là thứ học viên mở mỗi ngày, không phải một mục trong trang hồ sơ.

    **Lần đọc này có ghi**, và đó là ngoại lệ có chủ ý — lý do đầy đủ ở
    `daily_tasks.grant_rewards`. Nó an toàn vì tất định: `source_id` sinh từ
    (người, ngày, khe) nên gọi lại bao nhiêu lần cũng chỉ trao một lần.
    """
    profile = ensure_profile(db, current_user)
    day, tasks = tasks_for(db, current_user.id, profile.timezone)
    awarded = grant_rewards(db, current_user.id, profile.timezone, day, tasks)

    # Ruby đi cùng chỗ này chứ không có đường đọc riêng, vì cùng một lý do khiến
    # `grant_rewards` được phép ghi trong một lần đọc: đây là điểm chạm mỗi ngày
    # của người học, và cả hai khoản đều tất định nên gọi lại không trao thêm.
    #
    # Chuỗi ngày lấy từ `gather_stats`, tức là CÙNG con số hiển thị trên hồ sơ —
    # một phép đếm thứ hai ở đây sẽ trả thưởng vào một ngày khác với ngày thanh
    # chuỗi ngày sáng lên, và không có gì báo.
    ruby_awarded = ruby_daily.grant_all_tasks_done(db, current_user.id, day, tasks)
    ruby_awarded += ruby_daily.grant_streak_milestone(
        db, current_user.id, gather_stats(db, current_user.id, profile.timezone).current_streak
    )
    if awarded or ruby_awarded:
        db.commit()
    return DailyTasksPublic(
        date=day,
        tasks=[
            DailyTaskPublic(
                slot_id=str(t.slot_id),
                kind=t.kind,  # type: ignore[arg-type]
                label=t.label,
                target=t.target,
                progress=t.progress,
                done=t.done,
                xp=t.xp,
            )
            for t in tasks
        ],
        xp_awarded=awarded,
        ruby_awarded=ruby_awarded,
    )


@router.get("/progression/badges", response_model=BadgesPublic)
def read_badges(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BadgesPublic:
    """Cả 15 badge, đã mở lẫn chưa, kèm tiến độ tới ngưỡng.

    Trả về cả badge chưa mở là chủ ý: một trang chỉ hiện thứ đã đạt thì không nói
    được còn gì phía trước, mà đó mới là thứ khiến người ta quay lại.

    **Lần đọc này có ghi**, cùng ngoại lệ có chủ ý như `GET /daily-tasks`: badge
    vừa đủ điều kiện được ghi một hàng để lần sau biết nó không còn mới. An toàn
    vì khoá chính `(user_id, code)` khiến lần ghi thứ hai không thể xảy ra.
    """
    profile = ensure_profile(db, current_user)
    statuses = evaluate(db, current_user.id, profile.timezone)
    if record_new(db, current_user.id, statuses):
        db.commit()
    return BadgesPublic(
        badges=[
            BadgePublic(
                code=s.code,
                label=s.label,
                hint=s.hint,
                icon=s.icon,  # type: ignore[arg-type]
                image_url=s.image_url,
                target=s.target,
                progress=s.progress,
                earned=s.earned,
                awarded_at=s.awarded_at,
                seen=s.seen,
            )
            for s in statuses
        ],
        earned_count=sum(1 for s in statuses if s.earned),
        unseen_count=sum(1 for s in statuses if s.earned and not s.seen),
    )


@router.post("/progression/badges/seen", status_code=status.HTTP_204_NO_CONTENT)
def mark_badges_seen(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Tắt chấm đỏ.

    Không nhận danh sách mã: nút này bấm từ trang badge, nơi tất cả đang hiển thị
    cùng lúc, nên "đã xem" đúng nghĩa đen. Nhận danh sách sẽ mời phía gọi gửi
    thiếu, và một badge sót lại giữ chấm đỏ vĩnh viễn trên một trang không còn gì
    mới.

    204 kể cả khi không có gì để đánh dấu: phía gọi đang nói "tôi đã xem trang
    này", và câu đó luôn đúng. 404 hay 409 ở đây chỉ buộc frontend viết một nhánh
    xử lý cho một tình huống không phải lỗi.
    """
    if mark_seen(db, current_user.id):
        db.commit()
