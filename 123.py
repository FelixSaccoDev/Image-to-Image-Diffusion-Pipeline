import subprocess
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from tkinter import (
    Tk, Frame, Button, Label, StringVar,
    Scrollbar, Canvas, Checkbutton, IntVar,
    messagebox
)
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import os

def get_authors(min_commits=10):
    # Run git shortlog -sne to get authors with commit counts
    result = subprocess.run(
        ['git', 'shortlog', '-sne'],
        capture_output=True, text=True, encoding='utf-8'
    )
    if result.returncode != 0:
        raise RuntimeError("Git command failed. Run this script inside a git repo.")
    
    authors = []
    for line in result.stdout.strip().split('\n'):
        if not line.strip():
            continue
        # split on tab (shortlog output normally: "<count>\t<Name> <email>")
        parts = line.strip().split('\t', 1)
        if len(parts) != 2:
            continue
        count_str, rest = parts
        try:
            count = int(count_str.strip())
        except ValueError:
            continue
        if count >= min_commits:
            authors.append((count, rest.strip()))
    return authors

def get_commit_counts_for_authors(emails):
    if not emails:
        return pd.DataFrame(columns=['date', 'count'])

    proc = subprocess.Popen(
        ['git', 'log', '--pretty=format:%ad %ae', '--date=short'],
        stdout=subprocess.PIPE, text=True, encoding='utf-8'
    )

    date_counts = {}
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        # split into date and email (first space separates date and email)
        parts = line.split(' ', 1)
        if len(parts) != 2:
            continue
        date, email = parts
        if email in emails:
            date_counts[date] = date_counts.get(date, 0) + 1
    proc.stdout.close()
    proc.wait()

    df = pd.DataFrame(
        [(pd.to_datetime(date), count) for date, count in date_counts.items()],
        columns=['date', 'count']
    )
    return df

def plot_year(df, year):
    df_year = df[df['date'].dt.year == year]

    full_dates = pd.date_range(start=f'{year}-01-01', end=f'{year}-12-31', freq='D')
    df_year = pd.merge(pd.DataFrame({'date': full_dates}),
                       df_year.groupby('date')['count'].sum().reset_index(),
                       on='date', how='left').fillna({'count': 0})
    df_year['count'] = df_year['count'].astype(int)

    # Map weekday so that Sun=0, Mon=1, ... Sat=6 (display labels accordingly)
    df_year['weekday'] = df_year['date'].dt.weekday.apply(lambda x: (x + 1) % 7)
    df_year['week'] = df_year['date'].dt.isocalendar().week

    # Handle days in late-December that belong to week 1 of next year:
    max_week = df_year['week'].max()
    df_year.loc[(df_year['date'].dt.month == 12) & (df_year['week'] == 1), 'week'] = max_week + 1

    pivot = df_year.pivot_table(index='weekday', columns='week', values='count', aggfunc='sum').fillna(0)
    pivot = pivot.reindex(range(7), fill_value=0)

    fig, ax = plt.subplots(figsize=(14, 3))
    cmap = plt.cm.Greens
    vmax = max(5, df_year['count'].max())
    norm = mcolors.Normalize(vmin=0, vmax=vmax)
    c = ax.pcolormesh(pivot.columns, pivot.index, pivot.values, cmap=cmap, norm=norm, shading='auto')

    ax.set_title(f"GitHub-style Commit Heatmap - {year}", fontsize=14)
    ax.set_yticks(range(7))
    ax.set_yticklabels(['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'])
    ax.set_xticks([])
    ax.invert_yaxis()

    cbar = fig.colorbar(c, ax=ax, orientation='vertical', fraction=0.03, pad=0.04)
    cbar.set_label('Number of commits')

    fig.tight_layout()
    return fig

class HeatmapApp:
    def __init__(self, root):
        self.root = root
        root.title("GitHub Commit Heatmap Viewer")

        self.authors = []
        self.vars = []
        self.data = pd.DataFrame(columns=['date', 'count'])
        self.years = []
        self.current_year_idx = 0
        self.current_fig = None
        self.canvas = None

        top_frame = Frame(root)
        top_frame.pack(side='top', fill='x', padx=10, pady=10)

        load_btn = Button(top_frame, text="Load Authors (≥10 commits)", command=self.load_authors)
        load_btn.pack(side='left')

        self.status_var = StringVar()
        self.status_label = Label(top_frame, textvariable=self.status_var, fg="green")
        self.status_label.pack(side='left', padx=10)

        self.checkbox_frame = Frame(root)
        self.checkbox_frame.pack(side='top', fill='x', padx=10)

        self.canvas_frame = Frame(root)
        self.canvas_frame.pack(side='top', fill='both', expand=True, padx=10, pady=10)

        self.checkbox_canvas = Canvas(self.checkbox_frame, height=150)
        self.checkbox_scrollbar = Scrollbar(self.checkbox_frame, orient='vertical', command=self.checkbox_canvas.yview)
        self.checkbox_inner = Frame(self.checkbox_canvas)

        self.checkbox_inner.bind(
            "<Configure>",
            lambda e: self.checkbox_canvas.configure(
                scrollregion=self.checkbox_canvas.bbox("all")
            )
        )

        self.checkbox_canvas.create_window((0, 0), window=self.checkbox_inner, anchor='nw')
        self.checkbox_canvas.configure(yscrollcommand=self.checkbox_scrollbar.set)

        self.checkbox_canvas.pack(side='left', fill='x', expand=True)
        self.checkbox_scrollbar.pack(side='right', fill='y')

        btn_frame = Frame(root)
        btn_frame.pack(side='top', pady=5)

        self.show_btn = Button(btn_frame, text="Show Heatmap for Selected", command=self.show_heatmap, state='disabled')
        self.show_btn.grid(row=0, column=0, padx=5)

        self.prev_btn = Button(btn_frame, text="<< Prev Year", command=self.prev_year, state='disabled')
        self.prev_btn.grid(row=0, column=1, padx=5)

        self.next_btn = Button(btn_frame, text="Next Year >>", command=self.next_year, state='disabled')
        self.next_btn.grid(row=0, column=2, padx=5)

        self.save_btn = Button(btn_frame, text="Save Current Heatmap as PNG", command=self.save_current, state='disabled')
        self.save_btn.grid(row=0, column=3, padx=5)

    def load_authors(self):
        self.status_var.set("Loading authors...")
        try:
            self.authors = get_authors()
        except Exception as e:
            self.status_var.set(f"Error: {e}")
            return

        for widget in self.checkbox_inner.winfo_children():
            widget.destroy()
        self.vars.clear()

        if not self.authors:
            self.status_var.set("No authors with >=10 commits found.")
            return

        for count, author_str in self.authors:
            var = IntVar(value=0)
            cb = Checkbutton(self.checkbox_inner, text=f"{author_str} ({count} commits)", variable=var)
            cb.pack(anchor='w')
            self.vars.append((var, author_str))
        self.status_var.set(f"Loaded {len(self.authors)} authors.")
        self.show_btn.config(state='normal')

    def show_heatmap(self):
        import re
        selected_emails = []
        for var, author_str in self.vars:
            if var.get() == 1:
                m = re.search(r'<([^>]+)>', author_str)
                if m:
                    selected_emails.append(m.group(1))
        if not selected_emails:
            messagebox.showwarning("No selection", "Please select at least one author.")
            return

        self.status_var.set("Loading commit data for selected authors...")
        self.data = get_commit_counts_for_authors(selected_emails)
        if self.data.empty:
            messagebox.showinfo("No commits", "No commits found for selected authors.")
            self.status_var.set("No commits found for selection.")
            self.clear_canvas()
            self.prev_btn.config(state='disabled')
            self.next_btn.config(state='disabled')
            self.save_btn.config(state='disabled')
            return

        self.years = sorted(self.data['date'].dt.year.unique())
        self.current_year_idx = 0
        self.update_navigation_buttons()
        self.plot_current_year()

    def plot_current_year(self):
        year = self.years[self.current_year_idx]
        if self.canvas:
            self.canvas.get_tk_widget().destroy()
        self.current_fig = plot_year(self.data, year)
        self.canvas = FigureCanvasTkAgg(self.current_fig, master=self.canvas_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        self.status_var.set(f"Showing heatmap for year {year}")
        self.save_btn.config(state='normal')

    def update_navigation_buttons(self):
        self.prev_btn.config(state='normal' if self.current_year_idx > 0 else 'disabled')
        self.next_btn.config(state='normal' if self.current_year_idx < len(self.years) - 1 else 'disabled')

    def prev_year(self):
        if self.current_year_idx > 0:
            self.current_year_idx -= 1
            self.plot_current_year()
            self.update_navigation_buttons()

    def next_year(self):
        if self.current_year_idx < len(self.years) - 1:
            self.current_year_idx += 1
            self.plot_current_year()
            self.update_navigation_buttons()

    def save_current(self):
        if not self.current_fig:
            messagebox.showwarning("No heatmap", "No heatmap to save!")
            return
        out_dir = os.path.join(os.getcwd(), 'heatmaps')
        os.makedirs(out_dir, exist_ok=True)
        year = self.years[self.current_year_idx]
        out_path = os.path.join(out_dir, f"heatmap_{year}.png")
        self.current_fig.savefig(out_path, dpi=300, bbox_inches='tight')
        self.status_var.set(f"Saved heatmap for {year} to:\n{out_path}")
        messagebox.showinfo("Saved", f"Heatmap saved:\n{out_path}")

    def clear_canvas(self):
        if self.canvas:
            self.canvas.get_tk_widget().destroy()
            self.canvas = None
        self.current_fig = None

if __name__ == "__main__":
    root = Tk()
    app = HeatmapApp(root)
    root.mainloop()
