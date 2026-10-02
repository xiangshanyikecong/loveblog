/*
 * Love Journal - a private journal + blog + real-time interaction platform for couples.
 * Copyright (C) 2026 Love Journal Contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

import XCTest

@testable import LoveCore

/// M1 content contracts — fixtures mirror `server/app/schemas/*.py` shapes,
/// including the three known traps: two visibility vocabularies, encrypted
/// album media answering `file_url: ""`, and `+00:00`/timezone-less dates.
final class ContentDTOTests: XCTestCase {
    typealias D = ContentDTOs

    private func iso(_ string: String) -> Date {
        let formatter = ISO8601DateFormatter()
        return formatter.date(from: string)!
    }

    func testDashboardDecodesAllSections() throws {
        let data = Data(
            """
            {"love_clock":{"days":866,"hours":10,"minutes":11,"seconds":12},
             "stats":{"article_count":3,"album_count":2,"event_count":1,"message_count":9},
             "couple":{"partner_a":{"role":"PartnerA","nickname":"我","avatar":"/uploads/a.jpg"},
                       "partner_b":null},
             "recent_events":[{"eid":"e1","title":"领证","date":"2024-05-20","type":"Anniversary",
                "creator_uid":"u1","creator_nickname":"我","is_important":true,"is_yearly_repeat":true,
                "visibility":"PartnersOnly","tags":[],"next_occurrence_days":230,
                "created_at":"2026-10-01T08:00:00+00:00"}],
             "latest_articles":[],"latest_albums":[],"latest_messages":[]}
            """.utf8
        )
        let dashboard = try LoveAPIClient.decode(D.Dashboard.self, from: data)
        XCTAssertEqual(dashboard.loveClock.days, 866)
        XCTAssertEqual(dashboard.stats.articleCount, 3)
        XCTAssertEqual(dashboard.couple.partnerA?.nickname, "我")
        XCTAssertEqual(dashboard.recentEvents.first?.nextOccurrenceDays, 230)
        XCTAssertTrue(dashboard.recentEvents.first!.isAnniversary)
    }

    func testEventDecodesNaiveDatetimeAndNullOccurrence() throws {
        let data = Data(
            """
            {"eid":"e2","title":"旅行","date":"2026-12-01","type":"Countdown",
             "creator_uid":"u1","creator_nickname":"我","is_important":false,
             "is_yearly_repeat":false,"visibility":"Public","tags":["出行"],
             "next_occurrence_days":null,"created_at":"2026-10-01T08:00:00"}
            """.utf8
        )
        let event = try LoveAPIClient.decode(D.Event.self, from: data)
        XCTAssertNil(event.nextOccurrenceDays)
        XCTAssertFalse(event.isAnniversary)
        // Timezone-less dev-DB timestamps decode as UTC.
        XCTAssertEqual(event.createdAt, iso("2026-10-01T08:00:00Z"))
    }

    func testArticleDetailDecodesBlocksAndNestedComments() throws {
        let data = Data(
            """
            {"aid":"a1","title":"第一次见面","excerpt":"摘要","status":"Published",
             "is_encrypted":false,"is_co_created":false,"partner_can_edit":true,
             "visibility":"partners_only","requires_password":false,"tags":["纪念"],
             "version":4,"author_uid":"u1","author_nickname":"我",
             "published_at":"2026-05-20T09:30:00.123456+00:00","created_at":"2026-05-19T09:30:00+00:00",
             "collaborator_uids":["u2"],
             "blocks":[
               {"bid":"b2","block_type":"Paragraph","content":"正文","sort_order":1,
                "author_uid":"u1","author_nickname":"我"},
               {"bid":"b1","block_type":"Heading","content":"标题","sort_order":0,
                "author_uid":"u1","author_nickname":"我"}],
             "comments":[
               {"cid":"c1","parent_cid":null,"content":"顶层","author_uid":"u2",
                "author_nickname":"另一半","mention_uids":[],
                "created_at":"2026-05-20T10:00:00+00:00",
                "replies":[{"cid":"c2","parent_cid":"c1","content":"回复","author_uid":"u1",
                  "author_nickname":"我","mention_uids":["u2"],
                  "created_at":"2026-05-20T10:05:00+00:00","replies":[]}]}]}
            """.utf8
        )
        let detail = try LoveAPIClient.decode(D.ArticleDetail.self, from: data)
        XCTAssertEqual(detail.sortedBlocks.map(\.bid), ["b1", "b2"])
        XCTAssertTrue(detail.sortedBlocks[0].isHeading)
        XCTAssertEqual(detail.comments.first?.replies.first?.cid, "c2")
        XCTAssertTrue(detail.isPublished)
    }

    func testAlbumDetailLockedMediaHasEmptyFileUrl() throws {
        let data = Data(
            """
            {"alb_id":"al1","title":"婚礼","description":null,"cover_url":"/uploads/c.jpg",
             "is_encrypted":false,"is_public":true,"visibility":"public",
             "requires_password":false,"tags":[],"author_uid":"u1","author_nickname":"我",
             "media_count":2,"created_at":"2026-06-01T00:00:00+00:00",
             "media_items":[
               {"media_id":"m1","media_type":"Image","file_url":"/uploads/1.jpg",
                "thumbnail_url":null,"file_size":1024,"mime_type":"image/jpeg","is_encrypted":false},
               {"media_id":"m2","media_type":"Video","file_url":"",
                "thumbnail_url":null,"file_size":null,"mime_type":null,"is_encrypted":true}],
             "comments":[]}
            """.utf8
        )
        let detail = try LoveAPIClient.decode(D.AlbumDetail.self, from: data)
        XCTAssertEqual(detail.mediaItems.count, 2)
        XCTAssertTrue(detail.mediaItems[1].isLocked)
        XCTAssertTrue(detail.mediaItems[1].isVideo)
    }

    func testMessageDecodesNullableAuthorAndVisitor() throws {
        let data = Data(
            """
            {"msg_id":"m1","content":"祝福你们！","is_public":true,"tags":[],
             "is_deleted":false,"version":1,
             "created_at":"2026-07-01T12:00:00+00:00","updated_at":"2026-07-01T12:00:00+00:00",
             "author_uid":null,"author_nickname":null,"visitor_name":"路人甲"}
            """.utf8
        )
        let message = try LoveAPIClient.decode(D.Message.self, from: data)
        XCTAssertEqual(message.displayAuthor, "路人甲")
    }

    func testTimelineListDecodesMomentsAndCountsComments() throws {
        let data = Data(
            """
            {"items":[
               {"mid":"mo1","author_uid":"u1","author_nickname":"我","content":"今天很好",
                "media_urls":["/uploads/1.jpg","/uploads/2.jpg"],"audio_url":null,
                "audio_duration_sec":null,"location":"上海","visibility":"Public",
                "tags":["日常"],"timestamp":"2026-09-30T18:00:00+00:00",
                "comments":[
                  {"cid":"c1","parent_cid":null,"content":"一条","author_uid":"u2",
                   "author_nickname":"另一半","mention_uids":[],
                   "created_at":"2026-09-30T19:00:00+00:00",
                   "replies":[{"cid":"c2","parent_cid":"c1","content":"两条","author_uid":"u1",
                     "author_nickname":"我","mention_uids":[],
                     "created_at":"2026-09-30T19:05:00+00:00","replies":[]}]}]}],
             "page":1,"page_size":20,"total":1,"has_next":false,"sort":"desc"}
            """.utf8
        )
        let list = try LoveAPIClient.decode(D.TimelineList.self, from: data)
        XCTAssertEqual(list.items.first?.mediaUrls.count, 2)
        XCTAssertEqual(list.items.first?.commentCount, 2)
        XCTAssertFalse(list.hasNext)
    }

    func testSearchResponseDecodesMixedTypes() throws {
        let data = Data(
            """
            {"items":[
               {"type":"article","id":"a1","title":"标题","snippet":"片段…","url":"/articles/a1",
                "date":"2026-05-20T09:30:00+00:00","tags":["纪念"],"visibility":"PartnersOnly",
                "is_encrypted":true,"author_nickname":"我"},
               {"type":"message","id":"m1","title":"留言开头","snippet":"内容","url":"/messages",
                "date":"2026-07-01T12:00:00+00:00","tags":[],"visibility":"Public",
                "is_encrypted":false,"author_nickname":null}],
             "total":2,"page":1,"page_size":20}
            """.utf8
        )
        let response = try LoveAPIClient.decode(D.SearchResponse.self, from: data)
        XCTAssertEqual(response.items.count, 2)
        XCTAssertNil(response.items[1].authorNickname)
    }

    func testNotificationListDecodesAndCountsUnread() throws {
        let data = Data(
            """
            {"items":[
               {"nid":"n1","type":"message.created","title":"新留言","body":"有人给你留言",
                "link":"/messages","source_type":"message","source_id":"m1",
                "is_read":false,"created_at":"2026-10-01T00:00:00+00:00","read_at":null}],
             "total":1,"unread_count":3}
            """.utf8
        )
        let list = try LoveAPIClient.decode(D.NotificationList.self, from: data)
        XCTAssertEqual(list.unreadCount, 3)
        XCTAssertFalse(list.items[0].isRead)
    }

    func testPageEnvelopeDecodes() throws {
        let data = Data(#"{"items":[{"eid":"e1","title":"t","date":"2026-01-01","type":"Countdown","creator_uid":"u","creator_nickname":"n","is_important":false,"is_yearly_repeat":false,"visibility":"Public","tags":[],"next_occurrence_days":null,"created_at":"2026-01-01T00:00:00Z"}],"total":1}"#.utf8)
        let page = try LoveAPIClient.decode(D.Page<D.Event>.self, from: data)
        XCTAssertEqual(page.total, 1)
        XCTAssertEqual(page.items.first?.title, "t")
    }

    func testOnThisDayDecodesYearGroups() throws {
        let data = Data(
            """
            {"date":"2026-10-02",
             "years":[{"year":2024,
                "articles":[{"aid":"a1","title":"那年今天","excerpt":null,"created_at":"2024-10-02T00:00:00Z"}],
                "albums":[],"songs":[{"song_id":"s1","name":"歌","artists":["歌手"],"cover_url":null,"played_at":"2024-10-02T00:00:00Z"}],
                "totals":{"articles":1,"albums":0,"songs":1}}],
             "totals":{"articles":1,"albums":0,"songs":1}}
            """.utf8
        )
        let memories = try LoveAPIClient.decode(D.OnThisDay.self, from: data)
        XCTAssertEqual(memories.years.first?.year, 2024)
        XCTAssertEqual(memories.years.first?.songs.first?.name, "歌")
    }
}
