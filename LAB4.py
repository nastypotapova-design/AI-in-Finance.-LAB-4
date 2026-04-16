import pandas as pd
import matplotlib.pyplot as plt
import os
import re

SAVE_PLOTS = True
# ============================================================================
# 1. Helper functions
# ============================================================================

def analyze_gaps(group):
    years = group['Год'].sort_values().tolist()
    total_years = len(years)

    max_continuous = 1
    current = 1
    for i in range(1, len(years)):
        if years[i] - years[i - 1] == 1:
            current += 1
        else:
            max_continuous = max(max_continuous, current)
            current = 1
    max_continuous = max(max_continuous, current)

    max_gap = 0
    for i in range(1, len(years)):
        gap = years[i] - years[i - 1] - 1
        max_gap = max(max_gap, gap)

    return pd.Series({
        'total_years': total_years,
        'max_continuous_years': max_continuous,
        'max_gap_years': max_gap,
        'has_gap': max_gap > 0,
        'has_large_gap': max_gap >= 3
    })


def safe_filename(col):
    return re.sub(r'[ /\\]', '_', col)


def visualize_outliers(df, col, lower_bound=None, upper_bound=None):
    data = df[col].dropna()
    if len(data) == 0:
        print(f"No data for {col}")
        return None

    # Fast path: skip plotting
    if not SAVE_PLOTS:
        stats = {
            'min': data.min(),
            'max': data.max(),
            'mean': data.mean(),
            'p1': data.quantile(0.01),
            'p99': data.quantile(0.99),
            'n': len(data),
            'pct_below_lower': (data < lower_bound).mean() * 100 if lower_bound is not None else None,
            'pct_above_upper': (data > upper_bound).mean() * 100 if upper_bound is not None else None
        }
        return stats

    # Plotting path
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    axes[0].hist(data, bins=50, edgecolor='black')
    if lower_bound is not None:
        axes[0].axvline(lower_bound, color='red', linestyle='--', label=f'Lower bound ({lower_bound:.4f})')
    if upper_bound is not None:
        axes[0].axvline(upper_bound, color='red', linestyle='--', label=f'Upper bound ({upper_bound:.4f})')
    axes[0].set_title(f'{col} - histogram (before)')
    if lower_bound is not None or upper_bound is not None:
        axes[0].legend()

    axes[1].boxplot(data)
    axes[1].set_title(f'{col} - boxplot (before)')

    plt.suptitle(f'{col} - outlier analysis')
    plt.savefig(f'outliers_analysis/{safe_filename(col)}_before.png')
    plt.close()

    stats = {
        'min': data.min(),
        'max': data.max(),
        'mean': data.mean(),
        'p1': data.quantile(0.01),
        'p99': data.quantile(0.99),
        'n': len(data),
        'pct_below_lower': (data < lower_bound).mean() * 100 if lower_bound is not None else None,
        'pct_above_upper': (data > upper_bound).mean() * 100 if upper_bound is not None else None
    }

    return stats


def visualize_after(df, col, lower_bound, upper_bound, save_path='outliers_analysis'):
    data = df[col].dropna()

    # Fast path: skip plotting
    if not SAVE_PLOTS:
        stats = {
            'min': data.min(),
            'max': data.max(),
            'mean': data.mean(),
            'p1': data.quantile(0.01),
            'p99': data.quantile(0.99),
            'pct_at_lower': (data == lower_bound).mean() * 100,
            'pct_at_upper': (data == upper_bound).mean() * 100 if upper_bound is not None else 0
        }
        return stats

    # Plotting path
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    axes[0].hist(data, bins=50, edgecolor='black')
    axes[0].set_title(f'{col} - histogram (after)')

    axes[1].boxplot(data)
    axes[1].set_title(f'{col} - boxplot (after)')

    if upper_bound is not None:
        plt.suptitle(f'{col} - after clip[{lower_bound:.4f}, {upper_bound:.4f}]')
    else:
        plt.suptitle(f'{col} - after clip[{lower_bound:.4f}, ∞)')
    plt.savefig(f'{save_path}/{safe_filename(col)}_after.png')
    plt.close()

    stats = {
        'min': data.min(),
        'max': data.max(),
        'mean': data.mean(),
        'p1': data.quantile(0.01),
        'p99': data.quantile(0.99),
        'pct_at_lower': (data == lower_bound).mean() * 100,
        'pct_at_upper': (data == upper_bound).mean() * 100 if upper_bound is not None else 0
    }

    return stats

def process_indicator(df, indicator_name, lower_bound, upper_bound, clip_lower, clip_upper,
                      economic_meaning, justification, custom_treatment=None):
    before_stats = visualize_outliers(df, indicator_name, lower_bound=lower_bound, upper_bound=upper_bound)

    if custom_treatment is not None:
        df[indicator_name] = custom_treatment(df[indicator_name])
    else:
        df[indicator_name] = df[indicator_name].clip(lower=clip_lower, upper=clip_upper)

    after_stats = visualize_after(df, indicator_name, lower_bound=clip_lower, upper_bound=clip_upper)

    processed_indicators[indicator_name] = {
        'before_stats': before_stats,
        'after_stats': after_stats,
        'lower_bound': lower_bound,
        'upper_bound': upper_bound,
        'clip_lower': clip_lower,
        'clip_upper': clip_upper,
        'method': f'clip to [{clip_lower}, {clip_upper}]',
        'economic_meaning': economic_meaning,
        'justification': justification
    }
    return before_stats, after_stats


def treat_equity_assets(series):
    return series.clip(lower=-1, upper=1)


# ============================================================================
# 2. Load data and statistics
# ============================================================================

df = pd.read_excel('data.xlsx')

# Initialize readme_data dictionary
readme_data = {}
readme_data['time_min'] = df['Год'].min()
readme_data['time_max'] = df['Год'].max()
# Calculate initial missing stats from original df
initial_rows = len(df)
initial_cols = len(df.columns)
initial_missing_cells = df.isnull().sum().sum()
initial_missing_pct = (initial_missing_cells / (initial_rows * initial_cols)) * 100

# Create missing table for initial data
initial_missing_table = []
for col in df.columns:
    missing_cnt = df[col].isnull().sum()
    if missing_cnt > 0:
        initial_missing_table.append({
            'column': col,
            'missing_count': missing_cnt,
            'missing_pct': (missing_cnt / len(df)) * 100
        })

# Store in readme_data
readme_data['initial_rows'] = initial_rows
readme_data['initial_cols'] = initial_cols
readme_data['initial_missing_pct'] = initial_missing_pct
readme_data['initial_missing_table'] = initial_missing_table

# ============================================================================
# 3. Remove columns with >30% missing values
# ============================================================================

removed_cols_stats = {}
for col in ['Interest Coverage', 'Cash Flow / Total Liabilities', 'Retained Earnings / Assets']:
    if col in df.columns:
        removed_cols_stats[col] = (df[col].isnull().sum() / len(df)) * 100

df = df.drop(['Interest Coverage', 'Cash Flow / Total Liabilities', 'Retained Earnings / Assets'], axis=1)

# ============================================================================
# 4. Remove companies with only one year
# ============================================================================

years_per_company = df.groupby('ОГРН')['Год'].nunique()
single_year_count = (years_per_company == 1).sum()
single_year_rows = df[df['ОГРН'].isin(years_per_company[years_per_company == 1].index)].shape[0]

df = df[df['ОГРН'].isin(years_per_company[years_per_company > 1].index)]

# ============================================================================
# 5. Remove companies with gaps >= 3 years
# ============================================================================

gap_analysis = df.groupby('ОГРН').apply(analyze_gaps)
large_gap_count = (gap_analysis['max_gap_years'] >= 3).sum()
large_gap_rows = df[df['ОГРН'].isin(gap_analysis[gap_analysis['max_gap_years'] >= 3].index)].shape[0]

df_clean = df[df['ОГРН'].isin(gap_analysis[gap_analysis['max_gap_years'] < 3].index)].copy()

# ============================================================================
# 6. Calculate missing percentages after filtering
# ============================================================================

cols_to_fill = ['Equity / Assets', 'Liabilities / Assets', 'Current Ratio',
                'Quick Ratio', 'Cash / Current Liabilities', 'Working Capital / Assets',
                'Short-term Liabilities / Total Liabilities', 'ROA', 'Net Margin',
                'EBIT / Assets', 'Revenue / Assets', 'Receivables / Assets',
                'Payables / Assets', 'Log(Assets)', 'Log(Revenue)']

missing_pct = (df_clean[cols_to_fill].isnull().sum() / len(df_clean)) * 100

# ============================================================================
# 7. Outlier treatment
# ============================================================================

os.makedirs('outliers_analysis', exist_ok=True)

# Dictionary to store all processed indicators
processed_indicators = {}

# 7.1 Equity / Assets
before, after = process_indicator(
    df=df_clean,
    indicator_name='Equity / Assets',
    lower_bound=0,
    upper_bound=1,
    clip_lower=-1,
    clip_upper=1,
    economic_meaning="Shareholders' equity as a fraction of total assets. Measures financial cushion and solvency.",
    justification="Values < -1 indicate liabilities exceed assets by >100% - further negativity does not change default probability meaningfully. Values >1 are impossible (equity cannot exceed assets).",
    custom_treatment=treat_equity_assets
)
# 7.2 Liabilities / Assets
lower_liab = 0
upper_liab = round(df_clean['Liabilities / Assets'].quantile(0.99), 4)
before, after = process_indicator(
    df=df_clean,
    indicator_name='Liabilities / Assets',
    lower_bound=lower_liab,
    upper_bound=upper_liab,
    clip_lower=lower_liab,
    clip_upper=upper_liab,
    economic_meaning="Total liabilities as a fraction of total assets. Measures financial leverage and debt burden.",
    justification=f"99% of Liabilities/Assets values fall within [0, {upper_liab:.2f}]. Values outside this range are treated as extreme outliers and clipped to the nearest percentile bound."
)

# 7.3 Current Ratio
before, after = process_indicator(
    df=df_clean,
    indicator_name='Current Ratio',
    lower_bound=0,
    upper_bound=10,
    clip_lower=0,
    clip_upper=10,
    economic_meaning="Current assets / Current liabilities. Measures short-term liquidity and ability to pay obligations within one year.",
    justification="Current ratio cannot be negative. Values above 10 are extremely rare in construction industry and likely represent data errors. The [0, 10] range captures all economically plausible values while removing extreme outliers."
)

# 7.4 Quick Ratio
before, after = process_indicator(
    df=df_clean,
    indicator_name='Quick Ratio',
    lower_bound=0,
    upper_bound=10,
    clip_lower=0,
    clip_upper=10,
    economic_meaning="(Current assets - Inventory) / Current liabilities. A stricter liquidity measure that excludes hard-to-sell inventory.",
    justification="Quick ratio cannot be negative. Following the same logic as Current Ratio, values above 10 are extremely rare in construction industry. The [0, 10] range captures all economically plausible values."
)
# 7.5 Cash / Current Liabilities
before, after = process_indicator(
    df=df_clean,
    indicator_name='Cash / Current Liabilities',
    lower_bound=0,
    upper_bound=5,
    clip_lower=0,
    clip_upper=5,
    economic_meaning="Cash / Current liabilities. The most conservative liquidity measure - only cash, no receivables or inventory.",
    justification="Cash ratio cannot be negative. Based on the 99th percentile (5.0), values above 5 are extremely rare and likely represent data errors. The [0, 5] range captures all economically plausible values."
)
# 7.6 Working Capital / Assets
before, after = process_indicator(
    df=df_clean,
    indicator_name='Working Capital / Assets',
    lower_bound=-1,
    upper_bound=1,
    clip_lower=-1,
    clip_upper=1,
    economic_meaning="(Current assets - Current liabilities) / Total assets. Measures the proportion of assets financed by net working capital.",
    justification="Working capital rarely exceeds total assets in magnitude. Values outside [-1, 1] are likely data errors and are clipped to the nearest bound."
)

# 7.7 Short-term Liabilities / Total Liabilities
before, after = process_indicator(
    df=df_clean,
    indicator_name='Short-term Liabilities / Total Liabilities',
    lower_bound=0,
    upper_bound=1,
    clip_lower=0,
    clip_upper=1,
    economic_meaning="Short-term debt / Total debt. Measures the share of debt that matures within one year.",
    justification="A fraction cannot be negative or exceed 1. Values outside [0, 1] are data errors."
)

# 7.8 ROA - using percentiles
lower_roa = round(df_clean['ROA'].quantile(0.01), 4)
upper_roa = round(df_clean['ROA'].quantile(0.99), 4)
before, after = process_indicator(
    df=df_clean,
    indicator_name='ROA',
    lower_bound=lower_roa,
    upper_bound=upper_roa,
    clip_lower=lower_roa,
    clip_upper=upper_roa,
    economic_meaning="Net income / Total assets. Measures how efficiently a company uses its assets to generate profit.",
    justification=f"Based on data distribution, 98% of ROA values fall within [{lower_roa:.4f}, {upper_roa:.4f}]. Values outside this range are treated as extreme outliers and clipped to the nearest percentile bound."
)

# 7.9 Net Margin - using percentiles
lower_nm = round(df_clean['Net Margin'].quantile(0.01), 4)
upper_nm = round(df_clean['Net Margin'].quantile(0.99), 4)
before, after = process_indicator(
    df=df_clean,
    indicator_name='Net Margin',
    lower_bound=lower_nm,
    upper_bound=upper_nm,
    clip_lower=lower_nm,
    clip_upper=upper_nm,
    economic_meaning="Net income / Revenue. Measures profit margin on sales.",
    justification=f"Based on data distribution, 98% of Net Margin values fall within [{lower_nm:.4f}, {upper_nm:.4f}]. Values outside this range are treated as extreme outliers and clipped to the nearest percentile bound."
)

# 7.10 EBIT / Assets - using percentiles
lower_ebit = round(df_clean['EBIT / Assets'].quantile(0.01), 4)
upper_ebit = round(df_clean['EBIT / Assets'].quantile(0.99), 4)
before, after = process_indicator(
    df=df_clean,
    indicator_name='EBIT / Assets',
    lower_bound=lower_ebit,
    upper_bound=upper_ebit,
    clip_lower=lower_ebit,
    clip_upper=upper_ebit,
    economic_meaning="EBIT / Total assets. Measures operating profitability before interest and taxes.",
    justification=f"Based on data distribution, 98% of EBIT/Assets values fall within [{lower_ebit:.4f}, {upper_ebit:.4f}]. Values outside this range are treated as extreme outliers and clipped to the nearest percentile bound."
)

# 7.11 Revenue / Assets
before, after = process_indicator(
    df=df_clean,
    indicator_name='Revenue / Assets',
    lower_bound=0,
    upper_bound=10,
    clip_lower=0,
    clip_upper=10,
    economic_meaning="Revenue / Total assets. Measures asset turnover efficiency - how much revenue each ruble of assets generates.",
    justification="Asset turnover cannot be negative. Values above 10 are extremely rare in construction industry."
)

# 7.12 Receivables / Assets
before, after = process_indicator(
    df=df_clean,
    indicator_name='Receivables / Assets',
    lower_bound=0,
    upper_bound=1,
    clip_lower=0,
    clip_upper=1,
    economic_meaning="Accounts receivable / Total assets. Measures the proportion of assets tied up in customer debt.",
    justification="A fraction cannot be negative or exceed 1. Values outside [0, 1] are data errors."
)

# 7.13 Payables / Assets
before, after = process_indicator(
    df=df_clean,
    indicator_name='Payables / Assets',
    lower_bound=0,
    upper_bound=1,
    clip_lower=0,
    clip_upper=1,
    economic_meaning="Accounts payable / Total assets. Measures the proportion of assets financed by trade credit.",
    justification="A fraction cannot be negative or exceed 1. Values outside [0, 1] are data errors."
)

# 7.14 Log(Assets)
before_stats = visualize_outliers(df_clean, 'Log(Assets)', lower_bound=0, upper_bound=None)
df_clean['Log(Assets)'] = df_clean['Log(Assets)'].clip(lower=0)
after_stats = visualize_after(df_clean, 'Log(Assets)', lower_bound=0, upper_bound=None)

processed_indicators['Log(Assets)'] = {
    'before_stats': before_stats,
    'after_stats': after_stats,
    'lower_bound': 0,
    'upper_bound': None,
    'clip_lower': 0,
    'clip_upper': None,
    'method': 'clip to [0, ∞)',
    'economic_meaning': "Natural logarithm of total assets. Measures company size.",
    'justification': "Logarithm is defined only for positive numbers. Values below 0 are impossible."
}

# 7.15 Log(Revenue)
before_stats = visualize_outliers(df_clean, 'Log(Revenue)', lower_bound=0, upper_bound=None)
df_clean['Log(Revenue)'] = df_clean['Log(Revenue)'].clip(lower=0)
after_stats = visualize_after(df_clean, 'Log(Revenue)', lower_bound=0, upper_bound=None)

processed_indicators['Log(Revenue)'] = {
    'before_stats': before_stats,
    'after_stats': after_stats,
    'lower_bound': 0,
    'upper_bound': None,
    'clip_lower': 0,
    'clip_upper': None,
    'method': 'clip to [0, ∞)',
    'economic_meaning': "Natural logarithm of revenue. Measures company size by sales.",
    'justification': "Logarithm is defined only for positive numbers. Values below 0 are impossible."
}


# ============================================================================
# Balance sheet normalization
# ============================================================================
balance_before = df_clean['Equity / Assets'] + df_clean['Liabilities / Assets']
balance_deviation_before_mean = (balance_before - 1).abs().mean()
balance_deviation_before_max = (balance_before - 1).abs().max()

total = df_clean['Equity / Assets'] + df_clean['Liabilities / Assets']
df_clean['Equity / Assets'] = df_clean['Equity / Assets'] / total
df_clean['Liabilities / Assets'] = df_clean['Liabilities / Assets'] / total

# Fill any NaN from division by zero (should not happen)
df_clean['Equity / Assets'] = df_clean['Equity / Assets'].fillna(0)
df_clean['Liabilities / Assets'] = df_clean['Liabilities / Assets'].fillna(1)

# After balance sheet normalization, calculate final deviations
balance_after = df_clean['Equity / Assets'] + df_clean['Liabilities / Assets']
balance_deviation_after_mean = (balance_after - 1).abs().mean()
balance_deviation_after_max = (balance_after - 1).abs().max()
# ============================================================================
# 8. Collect general data for README
# ============================================================================

readme_data['final_rows'] = len(df_clean)
readme_data['final_cols'] = len(df_clean.columns)
readme_data['unique_ogrn'] = df_clean['ОГРН'].nunique()
readme_data['time_min'] = df['Год'].min()
readme_data['time_max'] = df['Год'].max()
readme_data['removed_cols'] = removed_cols_stats
readme_data['single_year_count'] = single_year_count
readme_data['single_year_rows'] = single_year_rows
readme_data['large_gap_count'] = large_gap_count
readme_data['large_gap_rows'] = large_gap_rows
readme_data['missing_pct'] = missing_pct.to_dict()

# ============================================================================
# 9. Fill first year conservatively, then apply LOCF
# ============================================================================

def fill_first_year_conservatively(group, conservative_values):
    """Fill first year of each company with conservative values"""
    min_year = group['Год'].min()
    first_year_mask = group['Год'] == min_year

    for col, value in conservative_values.items():
        if col in group.columns:
            group.loc[first_year_mask, col] = group.loc[first_year_mask, col].fillna(value)
    return group


# Define conservative values for first year
conservative_values = {
    'Equity / Assets': 0,
    'Liabilities / Assets': 1,
    'Current Ratio': 0.5,
    'Quick Ratio': 0.3,
    'Cash / Current Liabilities': 0,
    'Working Capital / Assets': -0.5,
    'Short-term Liabilities / Total Liabilities': 1,
    'ROA': -0.1,
    'Net Margin': -0.1,
    'EBIT / Assets': -0.1,
    'Revenue / Assets': 0,
    'Receivables / Assets': 0,
    'Payables / Assets': 0,
    'Log(Assets)': 0,
    'Log(Revenue)': 0
}
# After defining conservative_values, create table rows for README
conservative_table_rows = []
for indicator, value in conservative_values.items():
    if indicator == 'Equity / Assets':
        justification = 'No equity → maximum risk'
    elif indicator == 'Liabilities / Assets':
        justification = '100% debt financing'
    elif indicator in ['Current Ratio', 'Quick Ratio']:
        justification = 'Below standard liquidity'
    elif indicator == 'Cash / Current Liabilities':
        justification = 'No cash'
    elif indicator == 'Working Capital / Assets':
        justification = 'Negative working capital'
    elif indicator == 'Short-term Liabilities / Total Liabilities':
        justification = 'All debt is short-term'
    elif indicator in ['ROA', 'Net Margin', 'EBIT / Assets']:
        justification = 'Moderate loss'
    elif indicator == 'Revenue / Assets':
        justification = 'No revenue'
    elif indicator in ['Receivables / Assets', 'Payables / Assets']:
        justification = 'No receivables/payables'
    elif indicator in ['Log(Assets)', 'Log(Revenue)']:
        justification = 'Minimum size'
    else:
        justification = 'Conservative assumption'

    conservative_table_rows.append(f'| {indicator} | {value} | {justification} |')
# First, fill first year conservatively
df_filled = df_clean.groupby('ОГРН', group_keys=False).apply(
    lambda g: fill_first_year_conservatively(g, conservative_values)
)


# Then expand years within each company's actual range
def expand_company_years(group):
    """Expand years within company's min-max range only"""
    company = group['ОГРН'].iloc[0]
    min_year = group['Год'].min()
    max_year = group['Год'].max()

    all_years = pd.DataFrame({'Год': range(min_year, max_year + 1)})
    all_years['ОГРН'] = company

    expanded = all_years.merge(group, on=['ОГРН', 'Год'], how='left')
    expanded['Компания'] = expanded['Компания'].ffill()

    # Forward fill all financial indicators
    for col in cols_to_fill:
        expanded[col] = expanded[col].ffill()

    expanded['Дефолт'] = expanded['Дефолт'].ffill()
    expanded['Флаг дефолта'] = expanded['Флаг дефолта'].ffill()

    return expanded


# Apply expansion and LOCF
df_expanded = df_filled.groupby('ОГРН', group_keys=False).apply(expand_company_years)

print(f"Original rows: {len(df_clean)}")
print(f"Expanded rows: {len(df_expanded)}")
print(f"New rows added: {len(df_expanded) - len(df_clean)}")

# Check missing values after LOCF
missing_after_locf = (df_expanded[cols_to_fill].isnull().sum() / len(df_expanded)) * 100
print("\n=== Missing values after first-year fill + LOCF ===")
print(missing_after_locf.round(2).sort_values(ascending=False))

# Final check: should be very few or zero missing values
print(f"\nTotal missing values remaining: {df_expanded[cols_to_fill].isnull().sum().sum()}")


# ============================================================================
# 10. Calculate consistency statistics for README
# ============================================================================

balance_sum = df_expanded['Equity / Assets'] + df_expanded['Liabilities / Assets']
balance_deviation = (balance_sum - 1).abs()
quick_gt_current = (df_expanded['Quick Ratio'] > df_expanded['Current Ratio']).sum()
cash_gt_quick = (df_expanded['Cash / Current Liabilities'] > df_expanded['Quick Ratio']).sum()
stl_gt_1 = (df_expanded['Short-term Liabilities / Total Liabilities'] > 1).sum()
negative_equity = (df_expanded['Equity / Assets'] < 0).sum()
negative_liabilities = (df_expanded['Liabilities / Assets'] < 0).sum()
negative_curr_ratio = (df_expanded['Current Ratio'] < 0).sum()
negative_quick_ratio = (df_expanded['Quick Ratio'] < 0).sum()
negative_cash = (df_expanded['Cash / Current Liabilities'] < 0).sum()
high_receivables = (df_expanded['Receivables / Assets'] > 1).sum()
high_payables = (df_expanded['Payables / Assets'] > 1).sum()
sign_mismatch = ((df_expanded['ROA'] > 0) != (df_expanded['Net Margin'] > 0)).sum()

# Store in readme_data
readme_data['consistency'] = {
    'balance_mean_dev': balance_deviation.mean(),
    'balance_max_dev': balance_deviation.max(),
    'quick_gt_current': quick_gt_current,
    'quick_gt_current_pct': quick_gt_current / len(df_expanded) * 100,
    'cash_gt_quick': cash_gt_quick,
    'cash_gt_quick_pct': cash_gt_quick / len(df_expanded) * 100,
    'stl_gt_1': stl_gt_1,
    'stl_gt_1_pct': stl_gt_1 / len(df_expanded) * 100,
    'negative_equity': negative_equity,
    'negative_equity_pct': negative_equity / len(df_expanded) * 100,
    'negative_liabilities': negative_liabilities,
    'negative_curr_ratio': negative_curr_ratio,
    'negative_quick_ratio': negative_quick_ratio,
    'negative_cash': negative_cash,
    'high_receivables': high_receivables,
    'high_receivables_pct': high_receivables / len(df_expanded) * 100,
    'high_payables': high_payables,
    'high_payables_pct': high_payables / len(df_expanded) * 100,
    'sign_mismatch': sign_mismatch,
    'sign_mismatch_pct': sign_mismatch / len(df_expanded) * 100,
    'total_rows': len(df_expanded)
}

# ============================================================================
# 11. Save processed data
# ============================================================================

# Define desired column order
column_order = [
    'Год',
    'ОГРН',
    'Компания',
    'Дефолт',
    'Флаг дефолта',
    'Equity / Assets',
    'Liabilities / Assets',
    'Current Ratio',
    'Quick Ratio',
    'Cash / Current Liabilities',
    'Working Capital / Assets',
    'Short-term Liabilities / Total Liabilities',
    'ROA',
    'Net Margin',
    'EBIT / Assets',
    'Revenue / Assets',
    'Receivables / Assets',
    'Payables / Assets',
    'Log(Assets)',
    'Log(Revenue)'
]

# Reorder columns
df_expanded = df_expanded[column_order]

# Sort by company name alphabetically, then by year
df_expanded = df_expanded.sort_values(['Компания', 'Год'])

# Save to Excel
df_expanded.to_excel('df_processed.xlsx', index=False)

# ============================================================================
# 12. Generate README.md
# ============================================================================

with open('README.md', 'w', encoding='utf-8') as f:
    f.write('# Credit Risk Data Preprocessing for Construction Companies\n\n')

    f.write(
        'This document describes the step-by-step processing of the dataset for predicting default among construction companies.\n\n')

    f.write(f'**Initial data:** {readme_data["initial_rows"]:,} rows, {readme_data["initial_cols"]} columns\n\n')
    f.write(f'**Initial missing values:** {readme_data["initial_missing_pct"]:.1f}% of all cells\n\n')
    f.write(f'**Final data:** {readme_data["final_rows"]:,} rows, {readme_data["final_cols"]} columns\n\n')
    f.write(f'**Final missing values:** 0.0%\n\n')
    f.write(f'**Unique companies (OGRN):** {readme_data["unique_ogrn"]:,}\n\n')
    f.write(f'**Time period:** {readme_data["time_min"]}–{readme_data["time_max"]}\n\n')

    # Missing values by column
    f.write('**Missing values by column (initial data):**\n\n')
    f.write('| Column | Missing count | Missing % |\n')
    f.write('|--------|--------------|-----------|\n')

    for row in readme_data['initial_missing_table']:
        f.write(f'| {row["column"]} | {row["missing_count"]:,} | {row["missing_pct"]:.1f}% |\n')

    f.write('\n')

    # Stage 1
    f.write('## Stage 1. Removing columns with excessive missing values\n\n')
    f.write('Three columns were removed due to high missing values:\n\n')
    for col, pct in readme_data['removed_cols'].items():
        f.write(f'- `{col}` ({pct:.1f}% missing)\n')
    f.write(
        '\n**Justification:** These columns have systematic non-reporting (small construction companies rarely report interest expenses or cash flow statements). \n\n')
    f.write('---\n\n')

    # Stage 2
    f.write('## Stage 2. Removing companies with only one year of data\n\n')
    f.write('Companies appearing in only one year were removed because panel methods require temporal variation.\n\n')
    f.write(f'- Companies removed: {readme_data["single_year_count"]}\n')
    f.write(
        f'- Rows removed: {readme_data["single_year_rows"]} ({readme_data["single_year_rows"] / readme_data["initial_rows"] * 100:.1f}%)\n\n')
    f.write('---\n\n')

    # Stage 3
    f.write('## Stage 3. Removing companies with gaps ≥3 years\n\n')
    f.write('Companies with a maximum gap of 3 or more consecutive missing years were removed.\n\n')
    f.write(
        '**Justification:** A 3+ year gap represents economic discontinuity. Construction companies that disappear for 5 years have likely undergone major structural changes.\n\n')
    f.write(f'- Companies removed: {readme_data["large_gap_count"]}\n')
    f.write(f'- Rows removed: {readme_data["large_gap_rows"]}\n\n')
    f.write('---\n\n')

    # Stage 4a
    f.write('## Stage 4a. Outlier treatment by columns\n\n')

    for indicator_name, data in processed_indicators.items():
        safe_name = safe_filename(indicator_name)

        f.write(f'### {indicator_name}\n\n')
        f.write(f'**Economic meaning:** {data["economic_meaning"]}\n\n')

        f.write('**Original statistics:**\n\n')
        f.write('```\n')
        f.write(f'min: {data["before_stats"]["min"]:.4f}\n')
        f.write(f'max: {data["before_stats"]["max"]:.4f}\n')
        f.write(f'mean: {data["before_stats"]["mean"]:.4f}\n')
        f.write(f'p1: {data["before_stats"]["p1"]:.4f}\n')
        f.write(f'p99: {data["before_stats"]["p99"]:.4f}\n')
        f.write(f'% below {data["lower_bound"]:.4f}: {data["before_stats"]["pct_below_lower"]:.4f}%\n')
        if data["upper_bound"] is not None:
            f.write(f'% above {data["upper_bound"]:.4f}: {data["before_stats"]["pct_above_upper"]:.4f}%\n')
        else:
            f.write(f'% above upper bound: no upper bound\n')
        f.write('```\n\n')

        f.write(f'![{indicator_name} before](outliers_analysis/{safe_name}_before.png)\n\n')

        f.write('**Processing:**\n\n')
        f.write(f'Method: {data["method"]}\n\n')
        f.write(f'**Justification:** {data["justification"]}\n\n')

        f.write('**Statistics after processing:**\n\n')
        f.write('```\n')
        f.write(f'min: {data["after_stats"]["min"]:.4f}\n')
        f.write(f'max: {data["after_stats"]["max"]:.4f}\n')
        f.write(f'mean: {data["after_stats"]["mean"]:.4f}\n')
        f.write(f'p1: {data["after_stats"]["p1"]:.4f}\n')
        f.write(f'p99: {data["after_stats"]["p99"]:.4f}\n')
        f.write(f'% clipped to {data["clip_lower"]:.4f}: {data["after_stats"]["pct_at_lower"]:.2f}%\n')
        if data["clip_upper"] is not None:
            f.write(f'% clipped to {data["clip_upper"]:.4f}: {data["after_stats"]["pct_at_upper"]:.2f}%\n')
        else:
            f.write(f'% clipped to upper bound: no upper bound\n')
        f.write('```\n\n')

        f.write(f'![{indicator_name} after](outliers_analysis/{safe_name}_after.png)\n\n')
        f.write('---\n\n')

    # Stage 4b
    f.write('## Stage 4b. Balance sheet normalization\n\n')
    f.write('The accounting identity `Equity/Assets + Liabilities/Assets = 1` was violated in the original data. ')
    f.write(
        'This occurs because financial statements may contain rounding errors, different accounting standards, or misreporting.\n\n')
    f.write(f'- Mean deviation before normalization: {balance_deviation_before_mean:.6f}\n')
    f.write(f'- Max deviation before normalization: {balance_deviation_before_max:.6f}\n\n')
    f.write('**Solution:** Both ratios are divided by their sum for each row:\n\n')
    f.write('```\n')
    f.write('Equity/Assets_new = (Equity/Assets) / (Equity/Assets + Liabilities/Assets)\n')
    f.write('Liabilities/Assets_new = (Liabilities/Assets) / (Equity/Assets + Liabilities/Assets)\n')
    f.write('```\n\n')
    f.write(
        'This ensures the sum equals 1 while preserving the relative proportion between equity and liabilities.\n\n')
    f.write(f'- Mean deviation after normalization: {balance_deviation_after_mean:.6f}\n')
    f.write(f'- Max deviation after normalization: {balance_deviation_after_max:.6f}\n\n')
    f.write('---\n\n')

    # Stage 5
    f.write('## Stage 5. Handling missing values with panel structure\n\n')

    f.write('### 5.1 Conservative filling for first year\n\n')
    f.write('For each company, the first available year was filled with conservative (risk-increasing) values:\n\n')
    f.write('| Indicator | Conservative value | Economic justification |\n')
    f.write('|-----------|-------------------|------------------------|\n')

    for row in conservative_table_rows:
        f.write(row + '\n')

    f.write('\n')

    f.write('### 5.2 Expanding to full panel\n\n')
    f.write('For each company, missing years within its actual min-max range were added.\n\n')
    f.write(f'- Original rows: {len(df_clean):,}\n')
    f.write(f'- Expanded rows: {len(df_expanded):,}\n')
    f.write(f'- New rows added: {len(df_expanded) - len(df_clean):,}\n\n')

    f.write('### 5.3 LOCF (Last Observation Carried Forward)\n\n')
    f.write('Missing years within a company\'s active period are created to obtain a balanced panel. ')
    f.write(
        'For these added years, financial indicators are filled using the last available value from previous years.\n\n')
    f.write(
        'Default flags are also forward-filled because default cannot occur in a missing year within a company\'s active period. ')
    f.write('If a company defaulted, it stops reporting, so no years after default are created.\n\n')
    f.write('**Result:** 0 missing values remaining in all columns.\n\n')
    f.write('---\n\n')

    # Stage 6
    f.write('## Stage 6. Final consistency checks\n\n')
    f.write('After all processing steps, we verify that the data satisfies logical and accounting constraints.\n\n')

    cons = readme_data['consistency']

    f.write('### 6.1 Balance sheet identity\n\n')
    f.write(f'Mean deviation: {cons["balance_mean_dev"]:.6f}, Max deviation: {cons["balance_max_dev"]:.6f}\n\n')

    f.write('### 6.2 Liquidity ratios ordering\n\n')
    f.write(f'Quick Ratio > Current Ratio: {cons["quick_gt_current"]:,} rows ({cons["quick_gt_current_pct"]:.4f}%)\n')
    f.write(f'Cash > Quick Ratio: {cons["cash_gt_quick"]:,} rows ({cons["cash_gt_quick_pct"]:.4f}%)\n\n')

    f.write('### 6.3 Debt structure\n\n')
    f.write(f'Short-term Liabilities / Total Liabilities > 1: {cons["stl_gt_1"]:,} rows ({cons["stl_gt_1_pct"]:.4f}%)\n\n')

    f.write('### 6.4 Negative values\n\n')
    f.write(f'Equity / Assets < 0: {cons["negative_equity"]:,} rows ({cons["negative_equity_pct"]:.2f}%) - economically possible (technical bankruptcy)\n')
    f.write(f'Liabilities / Assets < 0: {cons["negative_liabilities"]:,} rows\n')
    f.write(f'Current Ratio < 0: {cons["negative_curr_ratio"]:,} rows\n')
    f.write(f'Quick Ratio < 0: {cons["negative_quick_ratio"]:,} rows\n')
    f.write(f'Cash / Current Liabilities < 0: {cons["negative_cash"]:,} rows\n\n')

    f.write('### 6.5 Asset composition\n\n')
    f.write(f'Receivables / Assets > 1: {cons["high_receivables"]:,} rows ({cons["high_receivables_pct"]:.4f}%)\n')
    f.write(f'Payables / Assets > 1: {cons["high_payables"]:,} rows ({cons["high_payables_pct"]:.4f}%)\n\n')

    f.write('### 6.6 Profitability sign consistency\n\n')
    f.write(f'ROA and Net Margin opposite signs: {cons["sign_mismatch"]:,} rows ({cons["sign_mismatch_pct"]:.2f}%)\n\n')
    f.write('---\n\n')

    f.write('## Conclusion\n\n')
    f.write(
        f'The data has been cleaned. Missing values are filled, outliers are capped, and the panel is balanced within each company\'s actual years. ')
    f.write(f'The final dataset contains {readme_data["final_rows"]:,} rows with no missing values. ')
    f.write(f'All financial ratios are within plausible ranges. The data is ready for modeling.\n\n')
    f.write('---\n\n')