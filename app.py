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
st.title("📊 DSE 공급량 vs 판매량 현황 분석 (단위: GJ)")

try:
    with st.spinner("최신 데이터를 로딩하고 정확하게 집계하는 중입니다..."):
        df_sales, df_supply, df_temp = load_data()
        df_master = preprocess_data(df_sales, df_supply, df_temp)
    
    st.markdown("### 📅 분석 기간 설정")
    
    month_list = df_master['년월'].dt.strftime('%Y-%m').sort_values().unique().tolist()
    
    # 디폴트 시작월: 2017-01
    default_start_val = '2017-01' if '2017-01' in month_list else month_list[0]
    
    # 디폴트 종료월: 무조건 2025-12로 고정
    default_end_val = '2025-12'
    if default_end_val not in month_list:
        default_end_val = month_list[-1]
    
    col1, col2 = st.columns(2)
    with col1:
        start_month_str = st.selectbox("시작 월", options=month_list, index=month_list.index(default_start_val))
    with col2:
        end_month_str = st.selectbox("종료 월", options=month_list, index=month_list.index(default_end_val))
    
    start_date = pd.to_datetime(start_month_str)
    end_date = pd.to_datetime(end_month_str)
    
    mask = (df_master['년월'] >= start_date) & (df_master['년월'] <= end_date)
    df_filtered = df_master.loc[mask]

    st.markdown("---")
    st.subheader("1. 월별 공급량/판매량(GJ) 및 기온 추이")
    
    lag_active = st.toggle("🔄 1개월 Lagging 반영 (판매량 실적을 1개월 앞으로 당겨서 가정용 청구 시차 보정)")
    
    df_plot1 = df_master.copy()
    if lag_active:
        df_plot1['판매량'] = df_plot1['판매량'].shift(-1)
        sales_label = '판매량 (1개월 Lag)'
        supply_label = '공급량'
    else:
        sales_label = '판매량'
        supply_label = '공급량'
        
    mask_plot1 = (df_plot1['년월'] >= start_date) & (df_plot1['년월'] <= end_date)
    df_filtered_plot1 = df_plot1.loc[mask_plot1]
    
    fig1 = make_subplots(specs=[[{"secondary_y": True}]])
    fig1.add_trace(go.Scatter(x=df_filtered_plot1['년월'], y=df_filtered_plot1['공급량'], mode='lines+markers', name=supply_label, line=dict(color='#005b96', width=2), hovertemplate='%{y:,.0f} GJ'), secondary_y=False)
    fig1.add_trace(go.Scatter(x=df_filtered_plot1['년월'], y=df_filtered_plot1['판매량'], mode='lines+markers', name=sales_label, line=dict(color='#e67e22', width=2), hovertemplate='%{y:,.0f} GJ'), secondary_y=False)
    fig1.add_trace(go.Scatter(x=df_filtered_plot1['년월'], y=df_filtered_plot1['평균기온'], mode='lines+markers', name='평균기온', line=dict(color='#d62728', width=2, dash='dot'), hovertemplate='%{y:.1f} °C'), secondary_y=True)
    
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
    chart2_container = st.empty()

    st.markdown("---")
    st.subheader("3. 연간 누적 공급량 vs 판매량 차이(Gap) 분석 테이블 (GJ)")
    table3_container = st.empty()

    # === 연도별 월별 상세 비교 섹션 ===
    st.markdown("---")
    st.subheader("연도별 월별 상세 비교")

    all_years_list = sorted(df_master['연도'].unique().tolist())
    
    col_sel, col_empty = st.columns([1, 4])
    with col_sel:
        selected_detail_year = st.selectbox("분석 연도를 선택하세요", all_years_list, index=all_years_list.index(2025) if 2025 in all_years_list else len(all_years_list)-1)

    # --- 2번 그래프 렌더링 (테두리 하이라이트 삭제됨) ---
    with chart2_container:
        if period_choice == '연간':
            group_col = '연도'
        elif period_choice == '반기별':
            group_col = '반기명'
        else:
            group_col = '분기명'
            
        df_grouped = df_filtered_plot1.groupby(group_col)[['공급량', '판매량']].sum().reset_index()
        fig2 = go.Figure()
        
        # 기본 막대그래프 렌더링
        fig2.add_trace(go.Bar(x=df_grouped[group_col], y=df_grouped['공급량'], name=supply_label, marker_color='#005b96', hovertemplate='%{y:,.0f} GJ'))
        fig2.add_trace(go.Bar(x=df_grouped[group_col], y=df_grouped['판매량'], name=sales_label, marker_color='#e67e22', hovertemplate='%{y:,.0f} GJ'))
        
        fig2.update_layout(
            barmode='group', hovermode='x unified', margin=dict(l=0, r=0, t=30, b=50),
            legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5)
        )
        fig2.update_yaxes(title_text="누적 물량 (GJ)")
        st.plotly_chart(fig2, use_container_width=True)

    # --- 3번 테이블 렌더링 ---
    with table3_container:
        df_table = df_filtered_plot1.groupby('연도')[['공급량', '판매량']].sum().reset_index()
        df_table['차이(Gap) [공급-판매]'] = df_table['공급량'] - df_table['판매량']
        df_table['대비(%)'] = np.where(df_table['공급량'] > 0, (df_table['차이(Gap) [공급-판매]'] / df_table['공급량'] * 100), 0).round(2)
        
        def highlight_selected_row(row, selected_year):
            if row.get('연도') == selected_year:
                return ['background-color: #ffe082; font-weight: bold;' for _ in row.index]
            return ['' for _ in row.index]

        formatted_table = df_table.style.format({
            '공급량': '{:,.0f}', '판매량': '{:,.0f}', '차이(Gap) [공급-판매]': '{:,.0f}', '대비(%)': '{:.2f}%'
        })
        formatted_table = formatted_table.apply(highlight_selected_row, axis=1, selected_year=selected_detail_year)
        st.dataframe(formatted_table, use_container_width=True, hide_index=True)

    # --- 선택된 연도의 하단 상세 그래프 및 테이블 렌더링 ---
    df_detail_year = df_plot1[df_plot1['연도'] == selected_detail_year].sort_values('월').copy()

    if not df_detail_year.empty:
        full_months = pd.DataFrame({'월': range(1, 13)})
        df_detail_grouped = df_detail_year.groupby('월')[['공급량', '판매량']].sum().reset_index()
        df_detail_final = pd.merge(full_months, df_detail_grouped, on='월', how='left').fillna(0)
        df_detail_final['월명'] = [f"{m}월" for m in df_detail_final['월']]

        fig_detail = go.Figure()
        fig_detail.add_trace(go.Bar(
            x=df_detail_final['월명'], y=df_detail_final['공급량'], name=supply_label, marker_color='#005b96', hovertemplate='%{y:,.0f} GJ'
        ))
        fig_detail.add_trace(go.Bar(
            x=df_detail_final['월명'], y=df_detail_final['판매량'], name=sales_label, marker_color='#e67e22', hovertemplate='%{y:,.0f} GJ'
        ))

        fig_detail.update_layout(
            title=f"<b>{selected_detail_year}년 월별 상세 실적 (Jan-Dec)</b>",
            barmode='group', hovermode='x unified', margin=dict(l=0, r=0, t=50, b=50),
            legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5)
        )
        fig_detail.update_yaxes(title_text="물량 (GJ)")
        st.plotly_chart(fig_detail, use_container_width=True)

        # 월별 상세 데이터 계산
        df_detail_final['차이(Gap) [공급-판매]'] = df_detail_final['공급량'] - df_detail_final['판매량']
        df_detail_final['대비(%)'] = np.where(df_detail_final['공급량'] > 0, (df_detail_final['차이(Gap) [공급-판매]'] / df_detail_final['공급량'] * 100), 0).round(2)
        
        # 합계 계산 및 행 추가
        total_supply = df_detail_final['공급량'].sum()
        total_sales = df_detail_final['판매량'].sum()
        total_gap = total_supply - total_sales
        total_ratio = (total_gap / total_supply * 100) if total_supply > 0 else 0
        
        total_row = pd.DataFrame({
            '월명': ['합계'],
            '공급량': [total_supply],
            '판매량': [total_sales],
            '차이(Gap) [공급-판매]': [total_gap],
            '대비(%)': [total_ratio]
        })
        
        # 원본 데이터와 합계 데이터 합치기
        df_detail_display = pd.concat([df_detail_final[['월명', '공급량', '판매량', '차이(Gap) [공급-판매]', '대비(%)']], total_row], ignore_index=True)
        
        # 합계 행 하이라이트 함수
        def highlight_total_row(row):
            if row.get('월명') == '합계':
                return ['background-color: #ffe082; font-weight: bold; padding: 5px;' for _ in row.index]
            return ['' for _ in row.index]

        # 포맷 및 스타일 적용
        formatted_monthly_table = df_detail_display.style.format({
            '공급량': '{:,.0f}', '판매량': '{:,.0f}', '차이(Gap) [공급-판매]': '{:,.0f}', '대비(%)': '{:.2f}%'
        }).apply(highlight_total_row, axis=1)
        
        st.markdown(f"**{selected_detail_year}년 월별 수치 세부 현황**")
        st.dataframe(formatted_monthly_table, use_container_width=True, hide_index=True)

    else:
        st.warning(f"{selected_detail_year}년에 대한 데이터가 존재하지 않습니다.")

except Exception as e:
    st.error(f"데이터를 처리하는 중 오류가 발생했습니다: {e}")
