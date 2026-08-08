"""Built-in editable Tiptap templates converted from the LM700 DOCX templates."""


def _text(value: str) -> dict:
    return {"type": "text", "text": value}


def _paragraph(value: str = "") -> dict:
    return {"type": "paragraph", "content": [_text(value)]} if value else {"type": "paragraph"}


def _heading(value: str) -> dict:
    return {"type": "heading", "attrs": {"level": 1}, "content": [_text(value)]}


def _qa(kind: str, value: str = "") -> dict:
    node = {"type": "qaLine", "attrs": {"kind": kind}}
    if value:
        node["content"] = [_text(value)]
    return node


def _document(*nodes: dict) -> dict:
    return {"type": "doc", "content": list(nodes)}


def _person_fields(subject: str) -> tuple[dict, ...]:
    return (
        _paragraph(f"{subject}基本情况：姓名{{{{姓名}}}}    性别{{{{性别}}}}    年龄{{{{年龄}}}}"),
        _paragraph("民族{{民族}}"),
        _paragraph("工作单位{{工作单位}}"),
        _paragraph("职务{{职务}}    身份证号{{身份证号}}"),
        _paragraph("住址（联系地址）{{住址}}"),
    )


def _interview_template(title: str, subject: str, action: str) -> dict:
    return _document(
        _heading(title),
        _paragraph("（{{case_no}}）第{{session_no}}号"),
        _paragraph("第  页  共  页"),
        *_person_fields(subject),
        _paragraph(f"{action}机关：{{{{办案机关}}}}"),
        _paragraph(f"{action}人员：{{{{办案人员}}}}"),
        _paragraph(f"{action}时间：{{{{date}}}} {{{{开始时间}}}}至{{{{结束时间}}}}"),
        _paragraph(f"{action}地点：{{{{地点}}}}"),
        _paragraph(f"执法人员出示执法证件后{action}，{action}内容："),
        _qa("question", f"告知：我们是{{{{办案机关}}}}执法人员，出示执法证件，证件编号是{{{{执法证件号1}}}}、{{{{执法证件号2}}}}，现就你涉嫌{{{{案由}}}}一事向你了解情况，你要实事求是地回答，不得隐瞒、歪曲、夸大或缩小事实，否则由此产生的后果你要承担责任。听清楚了吗？"),
        _qa("answer"),
        _qa("question", "你在你单位从事什么工作？担任什么职务？"),
        _qa("answer"),
        _paragraph("以下空白"),
        _paragraph("当事人签名：{{当事人签名}}    办案人员签名：{{办案人员签名}}"),
        _paragraph("日期：{{date}}"),
        _paragraph("备注：本记录一式两联，第一联留存卷宗备查，第二联交当事人。"),
    )


def _appointment_template() -> dict:
    return _document(
        _heading("约谈笔录"),
        _paragraph("第  页  共  页"),
        _paragraph("谈话人一：姓名{{谈话人1姓名}}    单位及职务{{谈话人1单位职务}}"),
        _paragraph("谈话人二：姓名{{谈话人2姓名}}    单位及职务{{谈话人2单位职务}}"),
        _paragraph("被约谈人一：姓名{{姓名}}    性别{{性别}}    年龄{{年龄}}"),
        _paragraph("身份证（有效身份证件）号码：{{身份证号}}"),
        _paragraph("工作单位：{{工作单位}}    职务：{{职务}}"),
        _paragraph("联系地址：{{住址}}    联系电话：{{联系电话}}"),
        _paragraph("被约谈人二：姓名{{第二被约谈人姓名}}    性别{{第二被约谈人性别}}    年龄{{第二被约谈人年龄}}"),
        _paragraph("身份证（有效身份证件）号码：{{第二被约谈人身份证号}}"),
        _paragraph("工作单位：{{第二被约谈人工作单位}}    职务：{{第二被约谈人职务}}"),
        _paragraph("联系地址：{{第二被约谈人住址}}    联系电话：{{第二被约谈人联系电话}}"),
        _paragraph("约谈地点：{{地点}}"),
        _paragraph("约谈时间：{{date}} {{开始时间}}至{{结束时间}}"),
        _paragraph("约谈主要内容："),
        _qa("question"),
        _qa("answer"),
        _paragraph("被约谈人：{{当事人签名}}    记录人：{{记录人签名}}"),
        _paragraph("备注：被约谈人应当在每页笔录签名，并签署“以上记录属实”。"),
    )


def _criminal_rights_template() -> dict:
    lines = (
        "根据《中华人民共和国刑事诉讼法》的规定，在公安机关对案件进行侦查期间，犯罪嫌疑人有如下诉讼权利和义务：",
        "1、自愿如实供述自己的罪行，承认指控的犯罪事实，愿意接受处罚的，可以依法从宽处理。",
        "2、不通晓当地通用的语言文字时有权要求配备翻译人员，有权用本民族语言文字进行诉讼。",
        "3、对于公安机关及其侦查人员侵犯其诉讼权利和人身侮辱的行为，有权提出申诉或者控告。",
        "4、对于侦查人员、鉴定人、记录人、翻译人员有法定情形的，有权申请他们回避；对于驳回申请回避的决定，可以申请复议一次。",
        "5、自接受第一次讯问或者被采取强制措施之日起，有权委托律师作为辩护人。经济困难或者有其他原因没有委托辩护人的，可以向法律援助机构提出申请。",
        "6、在接受传唤、拘传、讯问时，有权要求饮食和必要的休息时间。",
        "7、对于采取强制措施超过法定期限的，有权要求解除强制措施。",
        "8、对于侦查人员的提问，应当如实回答。但是对与本案无关的问题，有拒绝回答的权利。在接受讯问时有权为自己辩解。",
        "9、核对讯问笔录的权利，笔录记载有遗漏或者差错，可以提出补充或者改正。",
        "10、未满18周岁的犯罪嫌疑人在接受讯问时有要求通知其法定代理人到场的权利。",
        "11、聋、哑的犯罪嫌疑人在接受讯问时有要求通晓聋、哑手势的人参加的权利。",
        "12、依法接受拘传、取保候审、监视居住、拘留、逮捕等强制措施和人身检查、搜查、扣押、鉴定等侦查措施。",
        "13、公安机关送达的各种法律文书经确认无误后，应当签名、捺指印。",
        "14、有权知道用作证据的鉴定意见的内容，可以申请补充鉴定或重新鉴定。",
        "本权利义务告知书我已看过□ / 本权利义务告知书已向我宣读过□",
        "被告知人：{{姓名}}    日期：{{date}}",
    )
    return _document(_heading("犯罪嫌疑人诉讼权利义务告知书"), *(_paragraph(line) for line in lines))


def _administrative_rights_template() -> dict:
    lines = (
        "根据《中华人民共和国治安管理处罚法》、《公安机关办理行政案件程序规定》以及其他相关法律、法规、规章的规定，在公安机关办理行政案件调查取证期间，违法嫌疑人、被侵害人及其他证人有如下权利和义务：",
        "一、对有法定回避情形的公安机关负责人、办案人民警察、鉴定人、翻译人员，案件当事人及其法定代理人有要求其回避的权利。",
        "二、对案件事实有如实陈述的义务，必须如实提供证据、证言；对与案件无关的问题，有拒绝回答的权利。",
        "三、有使用本民族语言文字接受询问的权利。",
        "四、未成年人的被询问人有要求通知其父母或者其他监护人参加询问的权利。",
        "五、聋哑的被询问人在被询问时有要求通晓手语的人提供帮助的权利。",
        "六、不通晓当地通用的语言文字的被询问人在被询问时，有要求配备翻译人员的权利。",
        "七、有陈述和申辩的权利。",
        "八、有自行提供书面材料的权利。",
        "九、有核对询问笔录的权利，认为笔录有遗漏、差错的，有权要求补充或者更正。",
        "十、对涉及国家秘密、商业秘密或个人隐私的，公安机关将予以保密。",
        "十一、对公安机关及其人民警察不严格执法或有违法违纪行为的，有权向上一级公安机关或者人民检察院、行政监察机关检举、控告。",
        "本权利义务告知书已向我宣读过。",
        "签名：{{姓名}}    日期：{{date}}",
    )
    return _document(_heading("行政案件权利义务告知书"), *(_paragraph(line) for line in lines))


BUILTIN_TIPTAP_TEMPLATES = {
    "lm700_interrogation": {"name": "讯问笔录（LM700）", "transcript_type": "interrogation", "content": _interview_template("讯问笔录", "被讯问人", "讯问")},
    "lm700_inquiry": {"name": "询问笔录（LM700）", "transcript_type": "inquiry", "content": _interview_template("询问笔录", "被询问人", "询问")},
    "lm700_appointment": {"name": "约谈笔录（LM700）", "transcript_type": "other", "content": _appointment_template()},
    "lm700_criminal_rights": {"name": "犯罪嫌疑人诉讼权利义务告知书", "transcript_type": "other", "content": _criminal_rights_template()},
    "lm700_administrative_rights": {"name": "行政案件权利义务告知书", "transcript_type": "other", "content": _administrative_rights_template()},
}