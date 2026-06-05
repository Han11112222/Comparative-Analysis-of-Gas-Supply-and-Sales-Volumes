import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# 웹 페이지 기본 설정
st.set_page_config(page_title="공급량 vs 판매량 대시보드", layout="wide")

# 한글 폰트 설정 (Windows/Mac 대응)
# 참고: 배포하시는 서버(Linux 등) 환경에 따라 폰트 설정이 추가로 필요할 수 있습니다.
plt.rcParams['font.family'] = 'Malgun Gothic' # Mac은 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False

def convert_to_csv_url(url):
    base_url = url.split("/edit")[0]
    gid_part = ""
    if "gid=" in url:
        gid = url.split("gid=")[1].split("#")[0].split("&")[0]
        gid_part = f"&gid={gid}"
    return f"{base_url}/export?format=csv{gid_part}"

# 데이터를 캐싱하여 매번 새로고침할 때마다 로딩 시간이 길어지는 것을 방지합니다.
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
    df_sales_monthly = df_sales.groupby('년월')['판매량'].sum().reset_index()
    df_supply_monthly = df_supply.groupby('년월')['공급량'].sum().reset_index()
    df_temp_monthly = df_temp[['년월', '평균기온']].copy()
    
    df_merged = pd.merge(df_supply_monthly, df_sales_monthly, on='년월', how='inner')
    df_merged = pd.merge(df_merged, df_temp_monthly, on='년월', how='inner')
    
    df_merged['년월'] = pd.to_datetime(df_merged['년월'])
    df_merged = df_merged.sort_values('년월').reset_index(drop=True)
    
    df_merged['연도'] = df_merged['년월'].dt.year
    df_merged['월'] = df_merged['년월'].dt.month
    df_merged['분기'] = df_merged['년월'].dt.to_period('Q')
    
    df_merged['공급량_누적'] = df_merged.groupby('연도')['공급량'].cumsum()
    df_merged['판매량_누적'] = df_merged.groupby('연도')['판매량'].cumsum()
    
    return df_merged

# --- 시각화 함수들 ---

def plot_monthly_trend(df):
    fig, ax1 = plt.subplots(figsize=(14, 6))
    x = df['년월'].dt.strftime('%Y-%m')
    
    ax1.plot(x, df['공급량'], label='총 공급량', color='#1f77b4', marker='o', linewidth=2)
    ax1.plot(x, df['판매량'], label='총 판매량', color='#ff7f0e', marker='s', linewidth=2)
    ax1.set_xlabel('년월')
    ax1.set_ylabel('물량 (Volume)', color='black')
    ax1.set_xticklabels(x, rotation=45)
    ax1.legend(loc='upper left')
    ax1.grid(True, axis='y', linestyle='--', alpha=0.5)
    
    ax2 = ax1.twinx()
    ax2.plot(x, df['평균기온'], label='평균 기온', color='#d62728', linestyle='--', marker='x', alpha=0.7)
    ax2.set_ylabel('평균 기온 (°C)', color='#d62728')
    ax2.legend(loc='upper right')
    
    plt.title('월별 공급량 vs 판매량 및 기온 변화 추이', fontsize=14, pad=15)
    plt.tight_layout()
    st.pyplot(fig) # 스트림릿 화면에 그래프 송출

def plot_cumulative_ytd(df):
    fig, ax = plt.subplots(figsize=(12, 6))
    years = df['연도'].unique()
    colors = sns.color_palette("Set2", len(years))
    
    for i, year in enumerate(years):
        df_year = df[df['연도'] == year]
        months = df_year['월']
        
        ax.plot(months, df_year['공급량_누적'], label=f'{year} 공급 누적', color=colors[i], marker='o')
        ax.plot(months, df_year['판매량_누적'], label=f'{year} 판매 누적', color=colors[i], linestyle='--', marker='x')
        
    ax.set_title('연도별 공급량 및 판매량 누적(YTD) 비교 패턴', fontsize=14, pad=15)
    ax.set_xlabel('월 (Month)')
    ax.set_ylabel('누적 물량')
    ax.set_xticks(range(1, 13))
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax.grid(True, linestyle='--', alpha=0.5)
    plt.tight_layout()
    st.pyplot(fig)

def plot_quarterly_summary(df):
    df_quarterly = df.groupby(['연도', '분기'])[['공급량', '판매량']].sum().reset_index()
    df_quarterly['분기명'] = df_quarterly['분기'].astype(str)
    
    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(df_quarterly['분기명']))
    width = 0.35
    
    ax.bar(x - width/2, df_quarterly['공급량'], width, label='분기 공급량', color='#4bc0c0')
    ax.bar(x + width/2, df_quarterly['판매량'], width, label='분기 판매량', color='#ff6384')
    
    ax.set_title('분기별 누적 공급량 vs 판매량 비교', fontsize=14, pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(df_quarterly['분기명'], rotation=15)
    ax.set_ylabel('물량')
    ax.legend(loc='upper left')
    ax.grid(True, axis='y', linestyle='--', alpha=0.5)
    plt.tight_layout()
    st.pyplot(fig)

# --- 메인 실행 화면 구성 ---

st.title("📊 도시가스 공급량 및 판매량 비교분석 대시보드")
st.markdown("구글 스프레드시트의 실시간 데이터를 기반으로 월별, 누적, 분기별 실적을 분석합니다.")

try:
    with st.spinner("구글 스프레드시트에서 데이터를 불러오고 있습니다..."):
        df_sales, df_supply, df_temp = load_data()
        df_master = preprocess_data(df_sales, df_supply, df_temp)
    
    st.success("데이터 로딩 및 전처리 완료!")
    
    st.markdown("---")
    st.subheader("1. 월별 공급량/판매량 추이 및 기온 상관관계")
    plot_monthly_trend(df_master)
    
    st.markdown("---")
    st.subheader("2. 연간 누적(YTD) 공급량 및 판매량 비교")
    plot_cumulative_ytd(df_master)
    
    st.markdown("---")
    st.subheader("3. 분기별 누적 실적 비교")
    plot_quarterly_summary(df_master)

    # 필요시 원본 데이터 확인 가능하도록 토글 추가
    with st.expander("📝 전처리된 상세 데이터 표 보기"):
        st.dataframe(df_master)

except Exception as e:
    st.error(f"데이터를 불러오거나 처리하는 중 오류가 발생했습니다: {e}")
