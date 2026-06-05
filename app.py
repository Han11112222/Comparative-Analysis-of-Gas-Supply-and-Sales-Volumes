import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# 한글 폰트 설정 (Windows/Mac 대응 및 마이너스 기호 깨짐 방지)
plt.rcParams['font.family'] = 'Malgun Gothic' # Mac의 경우 'AppleGothic'
plt.rcParams['axes.unicode_minus'] = False

def convert_to_csv_url(url):
    """
    구글 스프레드시트 공유 링크를 Pandas가 읽을 수 있는 CSV 다운로드 링크로 변환합니다.
    gid(탭 ID) 정보가 있으면 해당 탭의 데이터를 가져옵니다.
    """
    base_url = url.split("/edit")[0]
    gid_part = ""
    if "gid=" in url:
        gid = url.split("gid=")[1].split("#")[0].split("&")[0]
        gid_part = f"&gid={gid}"
    return f"{base_url}/export?format=csv{gid_part}"

def load_data():
    # Han형님이 주신 구글 스프레드시트 원본 링크
    sales_url = "https://docs.google.com/spreadsheets/d/1-8RIPIkjnVXxoh5QJs6598nnHkWOGmrO655jr3b3g04/edit?gid=0#gid=0"
    supply_url = "https://docs.google.com/spreadsheets/d/1vS-a9XrbjjIznHxntuFIM6hmml6qTlR2Cayw77p_Rao/edit?gid=0#gid=0"
    temp_url = "https://docs.google.com/spreadsheets/d/13HrIz6OytYDykXeXzXJ02I6XbaKin1YaKBoO2kBd6Bs/edit?pli=1&gid=0#gid=0"
    
    # CSV 변환 링크 생성 후 데이터 로드
    print("데이터를 구글 스프레드시트에서 로드하는 중...")
    df_sales = pd.read_csv(convert_to_csv_url(sales_url))
    df_supply = pd.read_csv(convert_to_csv_url(supply_url))
    df_temp = pd.read_csv(convert_to_csv_url(temp_url))
    
    return df_sales, df_supply, df_temp

def preprocess_data(df_sales, df_supply, df_temp):
    """
    [데이터 구조 가정 및 전처리]
    공통적으로 '년월'(예: 2025-01 또는 202501) 컬럼이 있다고 가정합니다.
    실제 컬럼명이 다를 경우 아래 컬럼명을 스프레드시트에 맞게 수정해야 합니다.
    """
    # 1. 판매량 데이터 집계 (상품별 합산하여 월별 총판매량 계산)
    # 가정: 컬럼명이 '년월', '상품명', '판매량'인 경우
    df_sales_monthly = df_sales.groupby('년월')['판매량'].sum().reset_index()
    
    # 2. 공급량 데이터 집계
    # 가정: 컬럼명이 '년월', '상품명', '공급량'인 경우
    df_supply_monthly = df_supply.groupby('년월')['공급량'].sum().reset_index()
    
    # 3. 기온 데이터 전처리
    # 가정: 컬럼명이 '년월', '평균기온'인 경우
    df_temp_monthly = df_temp[['년월', '평균기온']].copy()
    
    # 4. 데이터 병합 (년월 기준)
    df_merged = pd.merge(df_supply_monthly, df_sales_monthly, on='년월', how='inner')
    df_merged = pd.merge(df_merged, df_temp_monthly, on='년월', how='inner')
    
    # 시계열 정렬 및 날짜 타입 변환
    df_merged['년월'] = pd.to_datetime(df_merged['년월'])
    df_merged = df_merged.sort_values('년월').reset_index(drop=True)
    
    # 분기 및 연도 컬럼 생성
    df_merged['연도'] = df_merged['년월'].dt.year
    df_merged['월'] = df_merged['년월'].dt.month
    df_merged['분기'] = df_merged['년월'].dt.to_period('Q')
    
    # 누적 데이터(YTD) 계산 (연도별 그룹화 후 누적합)
    df_merged['공급량_누적'] = df_merged.groupby('연도')['공급량'].cumsum()
    df_merged['판매량_누적'] = df_merged.groupby('연도')['판매량'].cumsum()
    
    return df_merged

def plot_monthly_trend(df):
    """1. 월별 공급량/판매량 추이 및 기온 상관관계 그래프 (이중 축 사용)"""
    fig, ax1 = plt.subplots(figsize=(14, 6))
    
    # 공급량, 판매량 바 차트 또는 라인 차트
    x = df['년월'].dt.strftime('%Y-%m')
    ax1.plot(x, df['공급량'], label='총 공급량', color='#1f77b4', marker='o', linewidth=2)
    ax1.plot(x, df['판매량'], label='총 판매량', color='#ff7f0e', marker='s', linewidth=2)
    ax1.set_xlabel('년월')
    ax1.set_ylabel('물량 (Volume)', color='black')
    ax1.tick_params(axis='y', labelcolor='black')
    ax1.set_xticklabels(x, rotation=45)
    ax1.legend(loc='upper left')
    ax1.grid(True, axis='y', linestyle='--', alpha=0.5)
    
    # 기온 데이터를 위한 우측 이중 축 생성
    ax2 = ax1.twinx()
    ax2.plot(x, df['평균기온'], label='평균 기온', color='#d62728', linestyle='--', marker='x', alpha=0.7)
    ax2.set_ylabel('평균 기온 (°C)', color='#d62728')
    ax2.tick_params(axis='y', labelcolor='#d62728')
    ax2.legend(loc='upper right')
    
    plt.title('월별 공급량 vs 판매량 및 기온 변화 추이', fontsize=14, fontweight='bold', pad=15)
    plt.tight_layout()
    plt.savefig('1_월별_추이_분석.png', dpi=300)
    plt.show()

def plot_cumulative_ytd(df):
    """2. 연간 누적(YTD) 공급량 및 판매량 비교 그래프"""
    plt.figure(figsize=(12, 6))
    
    # 연도별로 색상을 다르게 하여 누적 흐름 비교
    years = df['연도'].unique()
    colors = sns.color_palette("Set2", len(years))
    
    for i, year in enumerate(years):
        df_year = df[df['연도'] == year]
        months = df_year['월']
        
        plt.plot(months, df_year['공급량_누적'], label=f'{year} 공급 누적', color=colors[i], marker='o')
        plt.plot(months, df_year['판매량_누적'], label=f'{year} 판매 누적', color=colors[i], linestyle='--', marker='x')
        
    plt.title('연도별 공급량 및 판매량 누적(YTD) 비교 패턴', fontsize=14, fontweight='bold', pad=15)
    plt.xlabel('월 (Month)')
    plt.ylabel('누적 물량')
    plt.xticks(range(1, 13))
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.tight_layout()
    plt.savefig('2_연간_누적_분석.png', dpi=300)
    plt.show()

def plot_quarterly_summary(df):
    """3. 분기별 누적 실적 및 공급-판매 갭(Gap) 분석"""
    # 분기별 데이터 집계
    df_quarterly = df.groupby(['연도', '분기'])[['공급량', '판매량']].sum().reset_index()
    df_quarterly['공급-판매 갭'] = df_quarterly['공급량'] - df_quarterly['판매량']
    df_quarterly['분기명'] = df_quarterly['분기'].astype(str)
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(df_quarterly['분기명']))
    width = 0.35
    
    # 공급량 / 판매량 막대그래프
    ax.bar(x - width/2, df_quarterly['공급량'], width, label='분기 공급량', color='#4bc0c0')
    ax.bar(x + width/2, df_quarterly['판매량'], width, label='분기 판매량', color='#ff6384')
    
    ax.set_title('분기별 누적 공급량 vs 판매량 비교', fontsize=14, fontweight='bold', pad=15)
    ax.set_xticks(x)
    ax.set_xticklabels(df_quarterly['분기명'], rotation=15)
    ax.set_ylabel('물량')
    ax.legend(loc='upper left')
    ax.grid(True, axis='y', linestyle='--', alpha=0.5)
    
    plt.tight_layout()
    plt.savefig('3_분기별_누적_분석.png', dpi=300)
    plt.show()

if __name__ == "__main__":
    try:
        # 1. 데이터 로드
        df_sales, df_supply, df_temp = load_data()
        
        # 2. 데이터 전처리 및 마스터 테이블 생성
        df_master = preprocess_data(df_sales, df_supply, df_temp)
        
        # 데이터프레임 구조 확인 출력
        print("\n--- 전처리 완료 데이터 샘플 ---")
        print(df_master.head())
        
        # 3. 그래프 시각화 수행
        plot_monthly_trend(df_master)
        plot_cumulative_ytd(df_master)
        plot_quarterly_summary(df_master)
        
        print("\n모든 그래프 시각화 및 이미지 저장이 완료되었습니다.")
        
    except Exception as e:
        print(f"\n오류가 발생했습니다: {e}")
        print("팁: 구글 스프레드시트의 실제 컬럼명(예: 년월, 판매량, 공급량, 평균기온)이 코드 내 가정과 일치하는지 확인해 주세요.")
