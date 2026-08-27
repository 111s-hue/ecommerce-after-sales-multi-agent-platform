import re

INJECTION_PATTERNS = (
    r"忽略(以上|之前|所有).*(指令|规则|提示)",
    r"(泄露|输出|显示).*(system|系统).*(prompt|提示词)",
    r"(绕过|取消).*(权限|审批|安全)",
    r"(删除|修改).*(所有|其他用户).*(订单|数据)",
    r"ignore\s+(all\s+)?previous\s+instructions",
)


def detect_prompt_injection(text: str) -> str | None:
    normalized = text.strip().lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            return pattern
    return None
