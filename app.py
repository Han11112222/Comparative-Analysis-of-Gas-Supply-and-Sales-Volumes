import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# 웹 페이지 기본 설정 (가로로 넓게 쓰기)
st.set_page_config(page_title="공급량 vs 판매량 대시보드", layout="wide")

def convert_to_csv_url(url):
    base_url = url.split("/edit")[0]
    gid_part = ""
    if "gid=" in url:
        gid = url.split("gid=")[1].split("#")[0].split("&")[0]
        gid_part = f"&gid={gid}"
    return f"{base_url}/export?format=csv{gid_part}"

@st.cache_data
def load_data():
    sales_url = "https://docs.google.com/spreadsheets/d/1-8RIPIkjnVXxoh5QJs6598nnHkWOGmrO655jr3b3g04/edit?gid=0#gid=0"
    supply_url = "https://docs.google.com/spreadsheets/d/1vS-a9XrbjjIznHxntuFIM6hmml6qTlR2Cayw77p_Rao/edit?gid=0#gid=0"
    temp_url = "https://docs.google.com/spreadsheets/d/13HrIz6OytYDykXeXzXJ02I6XbaKin1YaKBoO2kBd6Bs/edit?pli=1&gid=0#gid=0"
    
    df_sales = pd.read_csv(convert_to_csv_url(sales_url))
    df_supply = pd.read_csv(convert_to_csv_url(supply_url))
    df_temp = pd.read_csv(convert_to_csv_url(temp_url))
    return df_sales, df_supply, df_temp

def preprocess_data(df_sales, df_supply, df_temp):
    # 1. 컬럼명 전처리 (안전하게 A열을 '년월'로 변경)
    for df in [df_sales, df_supply, df_temp]:
        df.columns = df.columns.str.strip()
        df.rename(columns={df.columns[0]: '년월'}, inplace=True)

    exclude_cols = ['년월', '연', '월', '평균기온', '날짜']
    
    # 2. 판매량 & 공급량 합산 (콤마 제거 및 형변환)
    sales_items = [c for c in df_sales.columns if c not in exclude_cols]
    for col in sales_items:
        df_sales[col] = df_sales[col].astype(str).str.replace(',', '', regex=False)
        df_sales[col] = pd.to_numeric(df_sales[col], errors='coerce').fillna(0)
    df_sales['총판매량'] = df_sales[sales_items].sum(axis=1)
    df_sales_monthly = df_sales[['년월', '총판매량']].rename(columns={'총판매량': '판매량'})
    
    supply_items = [c for c in df_supply.columns if c not in exclude_cols]
    for col in supply_items:
        df_supply[col] = df_supply[col].astype(str).str.replace(',', '', regex=False)
        df_supply[col] = pd.to_numeric(df_supply[col], errors='coerce').fillna(0)
    df_supply['총공급량'] = df_supply[supply_items].sum(axis=1)
    df_supply_monthly = df_supply[['년월', '총공급량']].rename(columns={'총공급량': '공급량'})
    
    # 3. 기온 데이터 처리
    if '평균기온' in df_temp.columns:
        df_temp_monthly = df_temp[['년월', '평균기온']]
    elif '평균기온' in df_supply.columns:
        df_temp_monthly = df_supply[['년월', '평균기온']]
    else:
        df_temp_monthly = pd.DataFrame({'년월': df_supply['년월'], '평균기온': 0})
            
    # 4. 데이터 병합
    df_merged = pd.merge(df_supply_monthly, df_sales_monthly, on='년월', how='inner')
    df_merged = pd.merge(df_merged, df_temp_monthly, on='년월', how='inner')
    
    # 5. 파생변수 생성 (날짜, 연, 월, 분기, 반기)
    df_merged['년월'] = pd.to_datetime(df_merged['년월'], errors='coerce')
    df_merged = df_merged.dropna(subset=['년월']).sort_values('년월').reset_index(drop=True)
    
    df_merged['연도'] = df_merged['년월'].dt.year
    df_merged['월'] = df_merged['년월'].dt.month
    df_merged['분기명'] = df_merged['연도'].astype(str) + '년 ' + df_merged['년월'].dt.quarter.astype(str) + '분기'
    df_merged['반기'] = np.where(df_merged['월'] <= 6, '상반기', '하반기')
    df_merged['반기명'] = df_merged['연도'].astype(str) + '년 ' + df_merged['반기']
    
    return df_merged

# --- UI 레이아웃 및 실행 ---
st.title("📊 도시가스 공급량 vs 판매량 동적 대시보드")

try:
    with st.spinner("구글 스프레드시트에서 데이터를 실시간으로 가져오는 중입니다..."):
        df_sales, df_supply, df_temp = load_data()
        df_master = preprocess_data(df_sales, df_supply, df_temp)
    
    # --- 1. 기간 선택 필터 (Sidebar or Main) ---
    st.markdown("### 📅 분석 기간 설정")
    min_date = df_master['년월'].min().to_pydatetime()
    max_date = df_master['년월'].max().to_pydatetime()
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("시작 월", value=min_date, min_value=min_date, max_value=max_date)
    with col2:
        end_date = st.date_input("종료 월", value=max_date, min_value=min_date, max_value=max_date)
    
    # 선택된 기간으로 데이터 필터링
    mask = (df_master['년월'] >= pd.to_datetime(start_date)) & (df_master['년월'] <= pd.to_datetime(end_date))
    df_filtered = df_master.loc[mask]

    st.markdown("---")

    # --- 2. 동적 월별 그래프 (Plotly 이중축) ---
    st.subheader("1. 월별 공급량/판매량 및 기온 추이 (확대/축소 가능)")
    
    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    
    fig1.add_trace(go.Scatter(x=df_filtered['년월'], y=df_filtered['공급량'], mode='lines+markers', name='공급량', line=dict(color='#1f77b4', width=2)), secondary_y=False)
    fig1.add_trace(go.Scatter(x=df_filtered['년월'], y=df_filtered['판매량'], mode='lines+markers', name='판매량', line=dict(color='#ff7f0e', width=2)), secondary_y=False)
    fig1.add_trace(go.Scatter(x=df_filtered['년월'], y=df_filtered['평균기온'], mode='lines+markers', name='평균기온', line=dict(color='#d62728', width=2, dash='dot')), secondary_y=True)
    
    fig1.update_layout(hovermode='x unified', margin=dict(l=0, r=0, t=30, b=0), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig1.update_yaxes(title_text="물량 (Volume)", secondary_y=False)
    fig1.update_yaxes(title_text="기온 (°C)", secondary_y=True)
    
    st.plotly_chart(fig1, use_container_width=True)
    
    st.markdown("---")

    # --- 3. 기간별 누적 막대그래프 (Plotly) ---
    st.subheader("2. 누적 실적 막대그래프 비교")
    
    # 사용자가 분기/반기/연간 중 선택
    period_choice = st.radio("보기 기준을 선택하세요:", ('연간', '반기별', '분기별'), horizontal=True)
    
    if period_choice == '연간':
        group_col = '연도'
    elif period_choice == '반기별':
        group_col = '반기명'
    else:
        group_col = '분기명'
        
    df_grouped = df_filtered.groupby(group_col)[['공급량', '판매량']].sum().reset_index()
    
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=df_grouped[group_col], y=df_grouped['공급량'], name='공급량 누적', marker_color='#4bc0c0'))
    fig2.add_trace(go.Bar(x=df_grouped[group_col], y=df_grouped['판매량'], name='판매량 누적', marker_color='#ff6384'))
    
    fig2.update_layout(barmode='group', hovermode='x unified', margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # --- 4. 연간 누적 차이(Gap) 분석 표 ---
    st.subheader("3. 연간 누적 공급량 vs 판매량 차이(Gap) 분석 테이블")
    
    df_table = df_filtered.groupby('연도')[['공급량', '판매량']].sum().reset_index()
    df_table['차이(Gap) [공급-판매]'] = df_table['공급량'] - df_table['판매량']
    # 갭 비율 계산 (공급량 대비 갭이 몇 %인지)
    df_table['손실율(%)'] = (df_table['차이(Gap) [공급-판매]'] / df_table['공급량'] * 100).round(2)
    
    # 천단위 콤마 포맷팅 적용을 위해 스타일링
    formatted_table = df_table.style.format({
        '공급량': '{:,.0f}',
        '판매량': '{:,.0f}',
        '차이(Gap) [공급-판매]': '{:,.0f}',
        '손실율(%)': '{:.2f}%'
    })
    
    st.dataframe(formatted_table, use_container_width=True)

except Exception as e:
    st.error(f"데이터를 처리하는 중 오류가 발생했습니다: {e}")
