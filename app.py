import streamlit as st
import requests
import yaml
import re
import pandas as pd

# 页面配置
st.set_page_config(page_title="AdsPower 地区分流助手", layout="wide")
st.title("🌍 SOCKS5 节点地区排序工具")

# --- 侧边栏：排序与参数设置 ---
with st.sidebar:
    st.header("⚙️ 配置参数")
    start_port = st.number_input("起始端口", value=42010, min_value=1024)

    st.subheader("📍 地区排序优先级")
    st.info("脚本将按以下顺序排列节点。你可以修改关键词，用逗号分隔。")
    # 定义默认排序顺序
    sort_order_raw = st.text_area("排序关键词序列", value="日本, 新加坡, 香港, 韩国, 美国,台湾",
                                  help="匹配节点名称中的文字")
    sort_order = [x.strip() for x in sort_order_raw.replace('，', ',').split(',')]

# --- 主界面 ---
col_in, col_out = st.columns([1, 1])

with col_in:
    st.subheader("1. 输入订阅链接")
    urls_input = st.text_area("一行一个订阅链接", height=200)
    generate_btn = st.button("🔄 按照地区排序并生成", use_container_width=True, type="primary")


def get_region_weight(name, order_list):
    """根据节点名称判断地区并返回权重，越小越靠前"""
    for index, keyword in enumerate(order_list):
        if keyword in name:
            return index
    return 999  # 未匹配到的排在最后


def process_and_sort(urls, s_port, order_list):
    all_proxies = []
    seen_names = set()
    headers = {'User-Agent': 'clash-verge/1.0.0 (Mihomo)'}

    # --- 修改起始点 ---


def process_and_sort(urls, s_port, order_list):
    all_proxies = []
    seen_names = set()
    headers = {'User-Agent': 'clash-verge/1.0.0 (Mihomo)'}

    # 1. 抓取所有节点
    for group_idx, url in enumerate(urls):
        if not url.strip(): continue
        try:
            resp = requests.get(url.strip(), headers=headers, timeout=10)
            data = yaml.safe_load(resp.text)
            if 'proxies' in data:
                for p in data['proxies']:
                    if re.search(r'流量|到期|官网|地址|重置|群组', p['name']): continue

                    # 标记来源信息（不影响连接）
                    p['origin'] = f"Airport_{group_idx + 1}"
                    p['group_idx'] = group_idx

                    name = p['name'].strip()
                    if name in seen_names: name = f"{name}_{len(seen_names)}"
                    p['name'] = name
                    seen_names.add(name)
                    all_proxies.append(p)
        except Exception as e:
            st.error(f"解析出错: {url[:30]}...")

    if not all_proxies: return None, None

    # 2. 双重排序：先按地区优先级，再按来源顺序
    all_proxies.sort(key=lambda x: (get_region_weight(x['name'], order_list), x['group_idx']))

    # 3. 生成配置
    config = {
        "allow-lan": True,
        "mode": "rule",
        "dns": {"enable": True, "enhanced-mode": "fake-ip", "nameserver": ["114.114.114.114"]},
        "proxies": all_proxies,
        "listeners": [
            {"name": f"port_{i}", "type": "mixed", "port": s_port + i, "proxy": p['name']}
            for i, p in enumerate(all_proxies)
        ]
    }

    # 4. 生成预览表（包含来源机场列）
    match_data = []
    for i, p in enumerate(all_proxies):
        match_data.append({
            "序号": i + 1,
            "来源机场": p['origin'],
            "地区分组": next((k for k in order_list if k in p['name']), "其他"),
            "节点名称": p['name'],
            "ADS 对应端口": s_port + i
        })
    df = pd.DataFrame(match_data)

    return yaml.dump(config, allow_unicode=True, sort_keys=False), df


# --- 修改结束点 ---


# --- 逻辑处理 ---
if generate_btn:
    if not urls_input:
        st.warning("请先输入订阅链接")
    else:
        urls = urls_input.split('\n')
        yaml_out, df_out = process_and_sort(urls, start_port, sort_order)
        if yaml_out:
            st.session_state.config_data = yaml_out
            st.session_state.match_df = df_out
            st.success("✅ 排序完成！")

# --- 输出区域 ---
with col_out:
    st.subheader("2. 预览与下载")
    if 'config_data' in st.session_state and st.session_state.config_data:
        st.download_button("💾 下载排序后的 YAML", st.session_state.config_data, "sorted_config.yaml",
                           use_container_width=True)
        st.write("📋 **端口分配表（已按地区归类）：**")
        st.dataframe(st.session_state.match_df, height=500, use_container_width=True)
# 浏览器UI打开：streamlit run app.py