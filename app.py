import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 웹 페이지 기본 설정
st.set_page_config(page_title="공급량 vs 판매량 대시보드", layout="wide")

def convert_to_csv_url(url):
    base_url = url.split("/edit")[0]
    gid_part = ""
    if "gid=" in url:
        gid = url.split("gid=")[1].split("#")[0].split("&")[0]
        gid_part = f"&gid={gid}"
    return f"{base_url}/export?format=csv{gid_part}"

@st.cache_data(ttl=60)
def load_data():
    sales_url = "https://docs.google.com/spreadsheets/d/1-8RIPIkjnVXxoh5QJs6598nnHkWOGmrO655jr3b3g04/edit?gid=0#gid=0"
    supply_url = "https://docs.google.com/spreadsheets/d/1vS-a9XrbjjIznHxntuFIM6hmml6qTlR2Cayw77p_Rao/edit?gid=0#gid=0"
    temp_url = "https://docs.google.com/spreadsheets/d/13HrIz6OytYDykXeXzXJ02I6XbaKin1YaKBoO2kBd6Bs/edit?pli=1&gid=0#gid=0"
    
    df_sales = pd.read_csv(convert_to_csv_url(sales_url))
    df_supply = pd.read_csv(convert_to_csv_url(supply_url))
    df_temp = pd.read_csv(convert_to_csv_url(temp_url))
    return df_sales, df_supply, df_temp

def preprocess_data(df_sales, df_supply, df_temp):
    # 1. 컬럼명 전처리
    for df in [df_sales, df_supply, df_temp]:
        df.columns = df.columns.str.strip()
        df.rename(columns={df.columns[0]: '년월'}, inplace=True)

    exclude_info = ['년월', '연', '월', '평균기온', '날짜']

    # 2. 판매량 합산
    sales_cols = [c for c in df_sales.columns if c not in exclude_info]
    for col in sales_cols:
        df_sales[col] = pd.to_numeric(df_sales[col].astype(str).str.replace(',', '', regex=False), errors='coerce').fillna(0)
    
    df_sales['총판매량'] = df_sales[sales_cols].sum(axis=1)
    df_sales_monthly = df_sales.groupby('년월')['총판매량'].sum().reset_index().rename(columns={'총판매량': '판매량'})
    
    # 3. 공급량 합산 및 단위 변환 (MJ -> GJ)
    supply_cols = [c for c in df_supply.columns if c not in exclude_info]
    for col in supply_cols:
        df_supply[col] = pd.to_numeric(df_supply[col].astype(str).str.replace(',', '', regex=False), errors='coerce').fillna(0)
        
    df_supply['총공급량'] = df_supply[supply_cols].sum(axis=1) / 1000
    df_supply_monthly = df_supply.groupby('년월')['총공급량'].sum().reset_index().rename(columns={'총공급량': '공급량'})
    
    # 4. 기온 데이터 처리
    if '평균기온' in df_temp.columns:
        df_temp_monthly = df_temp.groupby('년월')['평균기온'].mean().reset_index()
    elif '평균기온' in df_supply.columns:
        df_temp_monthly = df_supply.groupby('년월')['평균기온'].mean().reset_index()
    else:
        df_temp_monthly = pd.DataFrame({'년월': df_supply_monthly['년월'].unique(), '평균기온': 0})
            
    # 5. 데이터 병합
    df_merged = pd.merge(df_supply_monthly, df_sales_monthly, on='년월', how='outer').fillna(0)
    df_merged = pd.merge(df_merged, df_temp_monthly, on='년월', how='left').fillna(0)
    
    # 6. 파생변수 생성
    df_merged['년월'] = pd.to_datetime(df_merged['년월'], errors='coerce')
    df_merged = df_merged.dropna(subset=['년월']).sort_values('년월').reset_index(drop=True)
    
    df_merged['연도'] = df_merged['년월'].dt.year
    df_merged['월'] = df_merged['년월'].dt.month
    df_merged['분기명'] = df_merged['연도'].astype(str) + '년 ' + df_merged['년월'].dt.quarter.astype(str) + '분기'
    df_merged['반기'] = np.where(df_merged['월'] <= 6, '상반기', '하반기')
    df_merged['반기명'] = df_merged['연도'].astype(str) + '년 ' + df_merged['반기']
    
    return df_merged

# --- UI 레이아웃 및 실행 ---
st.title("📊 도시가스 공급량 vs 판매량 동적 대시보드 (단위: GJ)")

try:
    with st.spinner("최신 데이터를 로딩하고 정확하게 집계하는 중입니다..."):
        df_sales, df_supply, df_temp = load_data()
        df_master = preprocess_data(df_sales, df_supply, df_temp)
    
    st.markdown("### 📅 분석 기간 설정")
    min_date = df_master['년월'].min().date()
    max_date = df_master['년월'].max().date()
    
    # 디폴트 시작일을 2017년 1월 1일로 설정 (데이터가 더 짧을 경우를 대비해 min_date와 비교)
    default_start = pd.to_datetime('2017-01-01').date()
    if default_start < min_date:
        default_start = min_date
    
    col1, col2 = st.columns(2)
    with col1:
        # format="YYYY-MM" 속성을 통해 화면에 월까지만 표시되도록 설정
        start_date = st.date_input("시작 월", value=default_start, min_value=min_date, max_value=max_date, format="YYYY-MM")
    with col2:
        end_date = st.date_input("종료 월", value=max_date, min_value=min_date, max_value=max_date, format="YYYY-MM")
    
    mask = (df_master['년월'] >= pd.to_datetime(start_date)) & (df_master['년월'] <= pd.to_datetime(end_date))
    df_filtered = df_master.loc[mask]

    st.markdown("---")
    st.subheader("1. 월별 공급량/판매량(GJ) 및 기온 추이")
    
    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    fig1.add_trace(go.Scatter(x=df_filtered['년월'], y=df_filtered['공급량'], mode='lines+markers', name='공급량', line=dict(color='#1f77b4', width=2)), secondary_y=False)
    fig1.add_trace(go.Scatter(x=df_filtered['년월'], y=df_filtered['판매량'], mode='lines+markers', name='판매량', line=dict(color='#ff7f0e', width=2)), secondary_y=False)
    fig1.add_trace(go.Scatter(x=df_filtered['년월'], y=df_filtered['평균기온'], mode='lines+markers', name='평균기온', line=dict(color='#d62728', width=2, dash='dot')), secondary_y=True)
    
    fig1.update_layout(
        hovermode='x unified', 
        margin=dict(l=0, r=0, t=30, b=50),
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5)
    )
    fig1.update_yaxes(title_text="물량 (GJ)", secondary_y=False)
    fig1.update_yaxes(title_text="기온 (°C)", secondary_y=True)
    st.plotly_chart(fig1, use_container_width=True)
    
    st.markdown("---")
    st.subheader("2. 누적 실적 막대그래프 비교 (GJ)")
    
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
    
    fig2.update_layout(
        barmode='group', 
        hovermode='x unified', 
        margin=dict(l=0, r=0, t=30, b=50),
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5)
    )
    fig2.update_yaxes(title_text="누적 물량 (GJ)")
    st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    st.subheader("3. 연간 누적 공급량 vs 판매량 차이(Gap) 분석 테이블 (GJ)")
    
    df_table = df_filtered.groupby('연도')[['공급량', '판매량']].sum().reset_index()
    df_table['차이(Gap) [공급-판매]'] = df_table['공급량'] - df_table['판매량']
    # 명칭 변경: 손실율(%) -> 대비(%)
    df_table['대비(%)'] = np.where(df_table['공급량'] > 0, (df_table['차이(Gap) [공급-판매]'] / df_table['공급량'] * 100), 0).round(2)
    
    formatted_table = df_table.style.format({
        '공급량': '{:,.0f}',
        '판매량': '{:,.0f}',
        '차이(Gap) [공급-판매]': '{:,.0f}',
        '대비(%)': '{:.2f}%'
    })
    
    # hide_index=True를 통해 좌측 번호 열 삭제
    st.dataframe(formatted_table, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"데이터를 처리하는 중 오류가 발생했습니다: {e}")
