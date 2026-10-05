import os

html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SR University PaperHub - Question Paper Portal</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <!-- Supabase JS Client for Cloud Database & Storage -->
  <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
  <script src="./supabase_config.js"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            brandBlueDark: '#1e3a8a',
            brandBlue: '#2563eb',
            brandBlueHover: '#1d4ed8',
            brandBlueLight: '#eff6ff',
            brandBlueBorder: '#bfdbfe',
            brandSlate: '#0f172a',
            brandMuted: '#64748b'
          }
        }
      }
    }
  </script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');
    body { font-family: 'Inter', sans-serif; background-color: #f8fafc; color: #0f172a; }
    .font-mono-code { font-family: 'JetBrains Mono', monospace; }
    
    /* Clean custom scrollbars */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #f1f5f9; }
    ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
  </style>
</head>
<body class="min-h-screen flex flex-col antialiased bg-slate-50 text-slate-900">

  <!-- ================= 1. AUTHENTICATION VIEW (ALWAYS FIRST) ================= -->
  <div id="auth-view" class="min-h-screen flex flex-col justify-center py-12 sm:px-6 lg:px-8 bg-slate-50">
    <div class="sm:mx-auto sm:w-full sm:max-w-md text-center">
      <!-- SR University Crest / Icon -->
      <div class="w-16 h-16 bg-brandBlueDark text-white rounded-2xl flex items-center justify-center mx-auto shadow-md border border-blue-900">
        <i class="fa-solid fa-building-columns text-2xl"></i>
      </div>
      
      <h1 class="mt-4 text-2xl font-bold tracking-tight text-brandBlueDark">
        SR UNIVERSITY
      </h1>
      <p class="text-xs uppercase tracking-widest text-brandBlue font-semibold mt-0.5">
        PaperHub • Question Papers
      </p>
      <p class="mt-2 text-xs text-slate-500">
        Official exam papers for semester &amp; mid-term examinations
      </p>
    </div>

    <div class="mt-6 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
      <div class="bg-white py-8 px-6 sm:px-8 shadow-sm rounded-2xl border border-slate-200">
        
        <!-- Auth Tabs: Sign In / Registration -->
        <div class="flex border-b border-slate-200 mb-6 text-xs font-semibold">
          <button id="auth-tab-login" onclick="setAuthTab('login')" class="flex-1 pb-3 border-b-2 border-brandBlue text-brandBlue font-bold transition">
            Student Sign In
          </button>
          <button id="auth-tab-register" onclick="setAuthTab('register')" class="flex-1 pb-3 text-slate-400 hover:text-slate-600 transition">
            New Registration
          </button>
        </div>

        <form id="auth-form" onsubmit="handleAuthSubmit(event)" class="space-y-4">
          <!-- Full Name (Only for Registration) -->
          <div id="field-name" style="display: none;">
            <label class="block text-xs font-semibold text-slate-700 mb-1">Full Name *</label>
            <input id="login-name" type="text" placeholder="Enter your full name" class="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-brandBlue"/>
          </div>

          <!-- Enrollment Number (Only for Registration) -->
          <div id="field-roll" style="display: none;">
            <label class="block text-xs font-semibold text-slate-700 mb-1">Enrollment Number *</label>
            <div class="relative">
              <span class="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-400">
                <i class="fa-solid fa-id-card text-xs"></i>
              </span>
              <input id="login-roll" type="text" placeholder="e.g. 21SR1A0501" value="" class="w-full pl-9 pr-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs font-mono-code uppercase text-slate-800 focus:outline-none focus:ring-2 focus:ring-brandBlue"/>
            </div>
          </div>

          <!-- College Email Address -->
          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">College Email Address *</label>
            <div class="relative">
              <span class="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-400">
                <i class="fa-solid fa-envelope text-xs"></i>
              </span>
              <input id="login-email" type="email" required placeholder="e.g. student@sru.edu.in" value="" class="w-full pl-9 pr-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-brandBlue"/>
            </div>
          </div>

          <!-- Password -->
          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">Password *</label>
            <div class="relative">
              <span class="absolute inset-y-0 left-0 pl-3 flex items-center text-slate-400">
                <i class="fa-solid fa-lock text-xs"></i>
              </span>
              <input id="login-password" type="password" required placeholder="Enter your password (min 6 chars)" minlength="6" class="w-full pl-9 pr-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-brandBlue"/>
            </div>
          </div>

          <!-- Engineering Branch (Only for Registration) -->
          <div id="field-branch" style="display: none;">
            <label class="block text-xs font-semibold text-slate-700 mb-1">Engineering Branch *</label>
            <select id="login-branch" class="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-brandBlue">
              <option value="CSE">Computer Science &amp; Engineering (CSE)</option>
              <option value="AIML">Artificial Intelligence &amp; ML (AIML)</option>
              <option value="AIDS">AI &amp; Data Science (AIDS)</option>
              <option value="ECE">Electronics &amp; Communication (ECE)</option>
              <option value="EEE">Electrical &amp; Electronics (EEE)</option>
              <option value="MECH">Mechanical Engineering (MECH)</option>
              <option value="CIVIL">Civil Engineering (CIVIL)</option>
            </select>
          </div>

          <!-- Semester (Only for Registration) -->
          <div id="field-sem" style="display: none;">
            <label class="block text-xs font-semibold text-slate-700 mb-1">Current Semester *</label>
            <select id="login-sem" class="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-brandBlue">
              <option value="1">Semester 1 (I Year)</option>
              <option value="2">Semester 2 (I Year)</option>
              <option value="3">Semester 3 (II Year)</option>
              <option value="4">Semester 4 (II Year)</option>
              <option value="5" selected>Semester 5 (III Year)</option>
              <option value="6">Semester 6 (III Year)</option>
              <option value="7">Semester 7 (IV Year)</option>
              <option value="8">Semester 8 (IV Year)</option>
            </select>
          </div>

          <button id="auth-submit-btn" type="submit" class="w-full py-3 bg-brandBlue hover:bg-brandBlueHover text-white rounded-xl text-xs font-bold shadow-sm transition flex items-center justify-center space-x-2">
            <span>Sign In to Dashboard</span>
            <i class="fa-solid fa-arrow-right text-xs"></i>
          </button>
        </form>

        <!-- Guest / Quick Preview Button -->
        <div class="mt-4 text-center">
          <button type="button" onclick="continueAsGuest()" class="text-xs text-slate-500 hover:text-brandBlue font-medium transition">
            <i class="fa-solid fa-eye text-[11px] mr-1"></i> Browse Papers as Guest (Read-Only)
          </button>
        </div>

        <!-- Admin Portal Access Option -->
        <div class="mt-6 pt-4 border-t border-slate-100 text-center flex items-center justify-between text-xs text-slate-500">
          <button type="button" onclick="openAdminModal()" class="hover:text-brandBlue font-medium transition inline-flex items-center space-x-1.5">
            <i class="fa-solid fa-user-shield text-[11px]"></i>
            <span>Faculty &amp; Admin Access</span>
          </button>
          
          <div id="auth-cloud-status" class="inline-flex items-center space-x-1 text-[11px]">
            <span class="w-2 h-2 rounded-full bg-slate-300"></span>
            <span>Checking Cloud...</span>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- ================= 2. MAIN APPLICATION (NAVBAR + DASHBOARD) ================= -->
  <div id="app-view" style="display: none;" class="min-h-screen flex flex-col">
    
    <!-- Top Navigation Bar -->
    <header class="bg-white border-b border-slate-200 sticky top-0 z-40">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        
        <!-- Left: Logo and Portal Name -->
        <div class="flex items-center space-x-3 cursor-pointer" onclick="initDashboard()">
          <div class="w-10 h-10 bg-brandBlueDark text-white rounded-xl flex items-center justify-center shadow-sm border border-blue-900">
            <i class="fa-solid fa-building-columns text-base"></i>
          </div>
          <div>
            <div class="flex items-center space-x-2">
              <span class="text-base font-bold text-slate-900 leading-none">SR UNIVERSITY</span>
              <span class="text-[10px] font-bold uppercase tracking-wider bg-blue-50 text-brandBlue border border-blue-200 px-2 py-0.5 rounded-md">PaperHub</span>
            </div>
            <p class="text-[11px] text-slate-500 mt-0.5">Exam Papers &amp; Question Bank</p>
          </div>
        </div>

        <!-- Center: Live Cloud Status Indicator -->
        <div class="hidden md:flex items-center space-x-2 px-3 py-1 bg-slate-50 border border-slate-200 rounded-full text-xs text-slate-600">
          <span id="nav-cloud-dot" class="w-2 h-2 rounded-full bg-slate-300"></span>
          <span id="nav-cloud-label" class="font-medium text-[11px]">Connecting...</span>
        </div>

        <!-- Right Student Profile, Admin Badge & Logout -->
        <div class="flex items-center space-x-3">
          
          <!-- Upload Button -->
          <button type="button" onclick="openUploadModal()" class="px-3.5 py-2 bg-brandBlue hover:bg-brandBlueHover text-white rounded-xl text-xs font-bold shadow-sm transition flex items-center space-x-1.5">
            <i class="fa-solid fa-cloud-arrow-up text-xs"></i>
            <span>Upload Paper</span>
          </button>

          <!-- Admin Badge (Shown in Admin Mode) -->
          <button type="button" id="admin-badge" style="display: none;" onclick="openAdminModal()" class="items-center space-x-1.5 bg-amber-50 text-amber-800 border border-amber-300 px-2.5 py-1 rounded-lg text-[11px] font-bold">
            <i class="fa-solid fa-shield text-xs"></i>
            <span>Admin Panel</span>
          </button>

          <!-- Student Profile Pill -->
          <div id="user-profile-pill" class="flex items-center space-x-2 bg-slate-100 hover:bg-slate-200 px-3 py-1.5 rounded-xl text-xs transition cursor-default">
            <div class="w-6 h-6 rounded-full bg-brandBlue text-white flex items-center justify-center font-bold text-[10px]">
              <i class="fa-solid fa-user"></i>
            </div>
            <div class="text-left leading-tight hidden sm:block">
              <div id="nav-student-roll" class="font-bold text-slate-800 uppercase font-mono-code">21SR1A0501</div>
              <div id="nav-student-branch" class="text-[10px] text-slate-500">CSE • Sem 5</div>
            </div>
          </div>

          <!-- Sign Out Button -->
          <button type="button" onclick="handleLogout()" class="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-xl transition" title="Sign Out">
            <i class="fa-solid fa-arrow-right-from-bracket text-sm"></i>
          </button>
        </div>

      </div>
    </header>

    <!-- Main Content Area -->
    <main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">

      <!-- Campus Announcement Banner -->
      <div id="announcement-banner" class="bg-blue-50 border border-blue-200 rounded-2xl p-4 flex items-start sm:items-center justify-between gap-3 text-xs text-blue-900 shadow-sm">
        <div class="flex items-center space-x-3">
          <div class="w-8 h-8 rounded-xl bg-brandBlue text-white flex items-center justify-center shrink-0">
            <i class="fa-solid fa-bullhorn text-xs"></i>
          </div>
          <div>
            <strong class="font-bold">Campus Examination Notice:</strong>
            <span id="announcement-text" class="ml-1 text-blue-800">
              Welcome to SR University PaperHub! Browse past exam papers or upload new question papers to help your classmates.
            </span>
          </div>
        </div>
        <button type="button" id="btn-edit-announcement" style="display: none;" onclick="editAnnouncementPrompt()" class="shrink-0 px-2.5 py-1 bg-white hover:bg-blue-100 text-brandBlue border border-blue-200 rounded-lg text-xs font-semibold transition">
          <i class="fa-solid fa-pen-to-square text-[10px] mr-1"></i> Edit Notice
        </button>
      </div>

      <!-- Welcome Banner & Quick Actions -->
      <div class="bg-gradient-to-r from-brandBlueDark via-blue-900 to-blue-800 rounded-3xl p-6 sm:p-8 text-white shadow-md relative overflow-hidden">
        <div class="relative z-10 max-w-2xl">
          <span class="px-3 py-1 bg-white/10 text-blue-200 rounded-full text-xs font-medium uppercase tracking-wider backdrop-blur-sm">
            SRU Examination Question Bank
          </span>
          <h2 id="welcome-heading" class="text-xl sm:text-2xl font-extrabold mt-3 tracking-tight text-white">
            Welcome to PaperHub
          </h2>
          <p id="welcome-subheading" class="text-xs sm:text-sm text-blue-100 mt-1 leading-relaxed">
            Browse and download past examination question papers across all engineering regulations (R18 to R24).
          </p>

          <!-- Quick Action Buttons -->
          <div class="mt-5 flex flex-wrap items-center gap-2.5">
            <button type="button" onclick="openUploadModal()" class="px-4 py-2.5 bg-white text-brandBlueDark hover:bg-blue-50 rounded-xl text-xs font-bold shadow-sm transition flex items-center space-x-2">
              <i class="fa-solid fa-cloud-arrow-up text-xs"></i>
              <span>Upload New Question Paper</span>
            </button>
            <button type="button" onclick="focusSearch()" class="px-4 py-2.5 bg-white/10 hover:bg-white/20 text-white rounded-xl text-xs font-medium backdrop-blur-sm transition flex items-center space-x-2">
              <i class="fa-solid fa-magnifying-glass text-xs"></i>
              <span>Search By Subject</span>
            </button>
          </div>
        </div>

        <!-- Decorative Pattern -->
        <div class="absolute -right-10 -bottom-10 w-64 h-64 bg-white/5 rounded-full blur-2xl pointer-events-none"></div>
      </div>

      <!-- Metric Summary Cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3.5">
        <div class="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex items-center space-x-3">
          <div class="w-10 h-10 rounded-xl bg-blue-50 text-brandBlue flex items-center justify-center font-bold text-sm">
            <i class="fa-solid fa-file-invoice"></i>
          </div>
          <div>
            <div id="stat-total-papers" class="text-base font-bold text-slate-800">0</div>
            <div class="text-[11px] text-slate-500">Available Papers</div>
          </div>
        </div>

        <div class="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex items-center space-x-3">
          <div class="w-10 h-10 rounded-xl bg-blue-50 text-brandBlue flex items-center justify-center font-bold text-sm">
            <i class="fa-solid fa-graduation-cap"></i>
          </div>
          <div>
            <div id="stat-branch-papers" class="text-base font-bold text-slate-800">0</div>
            <div id="stat-branch-label" class="text-[11px] text-slate-500">For Your Branch</div>
          </div>
        </div>

        <div class="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex items-center space-x-3">
          <div class="w-10 h-10 rounded-xl bg-blue-50 text-brandBlue flex items-center justify-center font-bold text-sm">
            <i class="fa-solid fa-layer-group"></i>
          </div>
          <div>
            <div class="text-base font-bold text-slate-800">R18 - R24</div>
            <div class="text-[11px] text-slate-500">Active Regulations</div>
          </div>
        </div>

        <div class="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex items-center space-x-3">
          <div class="w-10 h-10 rounded-xl bg-blue-50 text-brandBlue flex items-center justify-center font-bold text-sm">
            <i class="fa-solid fa-download"></i>
          </div>
          <div>
            <div id="stat-total-downloads" class="text-base font-bold text-slate-800">0</div>
            <div class="text-[11px] text-slate-500">Total Downloads</div>
          </div>
        </div>
      </div>

      <!-- Filter & Search Control Panel -->
      <div class="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm mb-6 space-y-4">
        
        <!-- Search Bar & Dropdowns (Includes Added Regulations R18 to R24) -->
        <div class="flex flex-col md:flex-row md:items-center gap-3">
          <div class="flex-1 relative">
            <span class="absolute inset-y-0 left-0 pl-3.5 flex items-center text-slate-400 pointer-events-none">
              <i class="fa-solid fa-magnifying-glass text-xs"></i>
            </span>
            <input id="search-query" type="text" oninput="handleSearchFilter()" placeholder="Search by subject code (e.g. 22CS301) or title (e.g. Data Structures)..." class="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brandBlue"/>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <!-- Regulation Dropdown -->
            <select id="filter-regulation" onchange="handleSearchFilter()" class="px-3 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-brandBlue">
              <option value="ALL">All Regulations</option>
              <option value="R24">R24 Regulation</option>
              <option value="R22">R22 Regulation</option>
              <option value="R21">R21 Regulation</option>
              <option value="R20">R20 Regulation</option>
              <option value="R19">R19 Regulation</option>
              <option value="R18">R18 Regulation</option>
            </select>

            <!-- Semester Dropdown -->
            <select id="filter-semester" onchange="handleSearchFilter()" class="px-3 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-brandBlue">
              <option value="ALL">All Semesters</option>
              <option value="1">Semester 1</option>
              <option value="2">Semester 2</option>
              <option value="3">Semester 3</option>
              <option value="4">Semester 4</option>
              <option value="5">Semester 5</option>
              <option value="6">Semester 6</option>
              <option value="7">Semester 7</option>
              <option value="8">Semester 8</option>
            </select>

            <!-- Exam Type Dropdown -->
            <select id="filter-exam-type" onchange="handleSearchFilter()" class="px-3 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-brandBlue">
              <option value="ALL">All Exam Types</option>
              <option value="MID_1">Mid-Term 1</option>
              <option value="MID_2">Mid-Term 2</option>
              <option value="SEM_END">Semester End</option>
              <option value="SUPPLY">Supplementary</option>
            </select>

            <!-- Academic Year Dropdown -->
            <select id="filter-academic-year" onchange="handleSearchFilter()" class="px-3 py-2.5 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-brandBlue">
              <option value="ALL">All Academic Years</option>
              <option value="2025-2026">2025-2026</option>
              <option value="2024-2025">2024-2025</option>
              <option value="2023-2024">2023-2024</option>
              <option value="2022-2023">2022-2023</option>
              <option value="2021-2022">2021-2022</option>
              <option value="2020-2021">2020-2021</option>
            </select>
          </div>
        </div>

        <!-- Branch Filter Chips -->
        <div class="flex items-center space-x-1.5 overflow-x-auto pb-1 text-xs">
          <span class="text-xs font-semibold text-slate-500 mr-1 flex items-center">
            <i class="fa-solid fa-filter text-[10px] mr-1"></i> Branch:
          </span>
          <button type="button" onclick="setBranchFilter('ALL')" id="branch-chip-ALL" class="branch-chip px-3 py-1.5 rounded-lg font-medium text-xs bg-brandBlue text-white shadow-sm transition">
            All Branches
          </button>
          <button type="button" onclick="setBranchFilter('CSE')" id="branch-chip-CSE" class="branch-chip px-3 py-1.5 rounded-lg font-medium text-xs bg-slate-100 text-slate-600 hover:bg-slate-200 transition">
            CSE
          </button>
          <button type="button" onclick="setBranchFilter('AIML')" id="branch-chip-AIML" class="branch-chip px-3 py-1.5 rounded-lg font-medium text-xs bg-slate-100 text-slate-600 hover:bg-slate-200 transition">
            AIML
          </button>
          <button type="button" onclick="setBranchFilter('AIDS')" id="branch-chip-AIDS" class="branch-chip px-3 py-1.5 rounded-lg font-medium text-xs bg-slate-100 text-slate-600 hover:bg-slate-200 transition">
            AIDS
          </button>
          <button type="button" onclick="setBranchFilter('ECE')" id="branch-chip-ECE" class="branch-chip px-3 py-1.5 rounded-lg font-medium text-xs bg-slate-100 text-slate-600 hover:bg-slate-200 transition">
            ECE
          </button>
          <button type="button" onclick="setBranchFilter('EEE')" id="branch-chip-EEE" class="branch-chip px-3 py-1.5 rounded-lg font-medium text-xs bg-slate-100 text-slate-600 hover:bg-slate-200 transition">
            EEE
          </button>
          <button type="button" onclick="setBranchFilter('MECH')" id="branch-chip-MECH" class="branch-chip px-3 py-1.5 rounded-lg font-medium text-xs bg-slate-100 text-slate-600 hover:bg-slate-200 transition">
            MECH
          </button>
          <button type="button" onclick="setBranchFilter('CIVIL')" id="branch-chip-CIVIL" class="branch-chip px-3 py-1.5 rounded-lg font-medium text-xs bg-slate-100 text-slate-600 hover:bg-slate-200 transition">
            CIVIL
          </button>
        </div>

      </div>

      <!-- Question Papers Grid Header -->
      <div class="flex items-center justify-between mb-4">
        <div>
          <h3 class="text-base font-bold text-slate-900">Available Question Papers</h3>
          <p class="text-xs text-slate-500">Click any card to view full high-resolution question paper photo</p>
        </div>
        <div class="flex items-center space-x-2">
          <span id="papers-count-badge" class="px-2.5 py-1 bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg">
            0 papers available
          </span>
          <button id="btn-admin-clear" style="display: none;" type="button" onclick="adminClearAllPapers()" class="text-xs text-red-600 hover:text-red-800 transition flex items-center space-x-1" title="Admin action: Erase all papers">
            <i class="fa-solid fa-trash-can text-xs"></i>
            <span>Clear Archive</span>
          </button>
        </div>
      </div>

      <!-- Papers Cards Grid -->
      <div id="papers-grid" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        <!-- Rendered dynamically -->
      </div>

      <!-- Empty State -->
      <div id="empty-state" style="display: none;" class="bg-white rounded-2xl border border-slate-200 p-12 text-center my-6">
        <div class="w-16 h-16 bg-blue-50 text-brandBlue rounded-2xl flex items-center justify-center mx-auto mb-3 text-2xl">
          <i class="fa-solid fa-magnifying-glass"></i>
        </div>
        <h4 class="text-base font-bold text-slate-800">No Question Papers Found</h4>
        <p class="text-xs text-slate-500 max-w-sm mx-auto mt-1">
          No question papers matched your current filter criteria. Be the first to upload this paper for your classmates!
        </p>
        <button type="button" onclick="openUploadModal()" class="mt-4 px-4 py-2 bg-brandBlue hover:bg-brandBlueHover text-white rounded-xl text-xs font-bold transition inline-flex items-center space-x-1.5">
          <i class="fa-solid fa-cloud-arrow-up text-xs"></i>
          <span>Upload This Paper</span>
        </button>
      </div>

    </main>

    <!-- Footer (Strictly Collegiate, Clean) -->
    <footer class="bg-white border-t border-slate-200 py-6 mt-12">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-xs text-slate-500 space-y-1">
        <div class="flex items-center justify-center space-x-2 text-slate-700 font-medium">
          <i class="fa-solid fa-building-columns text-brandBlue"></i>
          <span>SR University PaperHub • Warangal, Telangana</span>
        </div>
        <p class="text-[11px] text-slate-400">
          Student Examination Paper Archive &amp; Contributor Portal • Security Hardened for University Deployment
        </p>
      </div>
    </footer>

  </div>

  <!-- ================= 3. IMAGE VIEWER MODAL ================= -->
  <div id="viewer-modal" style="display: none;" class="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-md flex flex-col p-2 sm:p-4">
    
    <!-- Top Bar -->
    <div class="bg-white/95 backdrop-blur rounded-2xl p-3 sm:p-4 mb-2 flex items-center justify-between border border-slate-200 shadow-lg">
      <div class="flex items-center space-x-3 overflow-hidden">
        <span id="viewer-subject-code" class="font-mono-code font-bold text-xs sm:text-sm px-2.5 py-1 bg-brandBlue text-white rounded-lg uppercase">
          22CS301
        </span>
        <div class="truncate">
          <h3 id="viewer-subject-name" class="font-bold text-xs sm:text-sm text-slate-900 truncate">
            Data Structures &amp; Algorithms
          </h3>
          <div id="viewer-meta" class="text-[11px] text-slate-500 mt-0.5 truncate">
            CSE • Semester 3 • Mid-Term 1 (R22) • 2025-2026
          </div>
        </div>
      </div>

      <!-- Controls & Close -->
      <div class="flex items-center space-x-1 sm:space-x-2 shrink-0">
        <button type="button" onclick="zoomViewer(0.2)" class="p-2 text-slate-700 hover:bg-slate-100 rounded-xl transition text-xs font-semibold flex items-center space-x-1" title="Zoom In">
          <i class="fa-solid fa-magnifying-glass-plus text-xs"></i>
          <span class="hidden sm:inline">Zoom In</span>
        </button>
        <button type="button" onclick="zoomViewer(-0.2)" class="p-2 text-slate-700 hover:bg-slate-100 rounded-xl transition text-xs font-semibold flex items-center space-x-1" title="Zoom Out">
          <i class="fa-solid fa-magnifying-glass-minus text-xs"></i>
          <span class="hidden sm:inline">Zoom Out</span>
        </button>
        <button type="button" onclick="rotateViewer()" class="p-2 text-slate-700 hover:bg-slate-100 rounded-xl transition text-xs font-semibold flex items-center space-x-1" title="Rotate 90°">
          <i class="fa-solid fa-rotate-right text-xs"></i>
          <span class="hidden sm:inline">Rotate</span>
        </button>
        <button type="button" onclick="downloadActivePaperImage()" class="p-2 bg-brandBlue hover:bg-brandBlueHover text-white rounded-xl transition text-xs font-bold flex items-center space-x-1" title="Download Image">
          <i class="fa-solid fa-arrow-down text-xs"></i>
          <span class="hidden sm:inline">Download</span>
        </button>
        <button type="button" onclick="closeViewerModal()" class="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition text-sm">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
    </div>

    <!-- Image Display Container -->
    <div class="flex-1 bg-slate-900 rounded-2xl overflow-auto flex items-center justify-center p-4 relative select-none">
      <img id="viewer-image" src="" alt="Question Paper" class="max-h-full max-w-full object-contain rounded-lg shadow-2xl transition-transform duration-150 origin-center"/>
    </div>

    <!-- Bottom Footer Meta Info -->
    <div class="mt-2 bg-white/95 backdrop-blur rounded-xl px-4 py-2 flex items-center justify-between text-[11px] text-slate-600 border border-slate-200">
      <div class="flex items-center space-x-4">
        <span>Uploaded by: <strong id="viewer-uploader" class="text-slate-800">Student</strong></span>
        <span>•</span>
        <span>Academic Year: <strong id="viewer-year" class="text-slate-800">2025-2026</strong></span>
        <span>•</span>
        <span>Max Marks: <strong id="viewer-marks" class="text-slate-800">30 Marks</strong></span>
      </div>
      <div class="font-mono-code text-[11px] text-slate-400">
        SR University Question Bank
      </div>
    </div>

  </div>

  <!-- ================= 4. UPLOAD QUESTION PAPER MODAL ================= -->
  <div id="upload-modal" style="display: none;" class="fixed inset-0 z-50 bg-slate-900/70 backdrop-blur-sm items-center justify-center p-4 overflow-y-auto">
    <div class="bg-white rounded-3xl max-w-lg w-full p-6 sm:p-7 shadow-2xl border border-slate-200 relative my-6">
      
      <!-- Close Button -->
      <button type="button" onclick="closeUploadModal()" class="absolute top-5 right-5 text-slate-400 hover:text-slate-600 p-1">
        <i class="fa-solid fa-xmark text-lg"></i>
      </button>

      <!-- Header -->
      <div class="flex items-center space-x-3 mb-5">
        <div class="w-10 h-10 rounded-2xl bg-blue-50 text-brandBlue flex items-center justify-center">
          <i class="fa-solid fa-cloud-arrow-up text-lg"></i>
        </div>
        <div>
          <h3 class="text-base font-bold text-slate-900">Upload Question Paper</h3>
          <p class="text-xs text-slate-500">Upload paper photo (JPG, PNG, WEBP, PDF up to 10MB)</p>
        </div>
      </div>

      <!-- Form -->
      <form id="paper-upload-form" onsubmit="handlePaperUploadSubmit(event)" class="space-y-3.5">
        
        <!-- Row 1: Branch & Semester -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">Engineering Branch *</label>
            <select id="up-branch" required class="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-brandBlue">
              <option value="CSE">Computer Science &amp; Engg (CSE)</option>
              <option value="AIML">Artificial Intelligence &amp; ML (AIML)</option>
              <option value="AIDS">AI &amp; Data Science (AIDS)</option>
              <option value="ECE">Electronics &amp; Comm. (ECE)</option>
              <option value="EEE">Electrical &amp; Electronics (EEE)</option>
              <option value="MECH">Mechanical Engg. (MECH)</option>
              <option value="CIVIL">Civil Engg. (CIVIL)</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">Semester *</label>
            <select id="up-semester" required class="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-brandBlue">
              <option value="1">Semester 1 (I Year)</option>
              <option value="2">Semester 2 (I Year)</option>
              <option value="3">Semester 3 (II Year)</option>
              <option value="4">Semester 4 (II Year)</option>
              <option value="5">Semester 5 (III Year)</option>
              <option value="6">Semester 6 (III Year)</option>
              <option value="7">Semester 7 (IV Year)</option>
              <option value="8">Semester 8 (IV Year)</option>
            </select>
          </div>
        </div>

        <!-- Row 2: Exam Type & Academic Regulation -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">Examination Type *</label>
            <select id="up-exam-type" required class="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-brandBlue">
              <option value="MID_1">Mid-Term 1 (Mid-1)</option>
              <option value="MID_2">Mid-Term 2 (Mid-2)</option>
              <option value="SEM_END">Semester End Exam</option>
              <option value="SUPPLY">Supplementary Exam</option>
            </select>
          </div>
          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">Academic Regulation *</label>
            <select id="up-regulation" required class="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-brandBlue">
              <option value="R24">R24 Regulation</option>
              <option value="R22" selected>R22 Regulation</option>
              <option value="R21">R21 Regulation</option>
              <option value="R20">R20 Regulation</option>
              <option value="R19">R19 Regulation</option>
              <option value="R18">R18 Regulation</option>
            </select>
          </div>
        </div>

        <!-- Row 3: Subject Code & Academic Year -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">Subject Code *</label>
            <input id="up-subject-code" type="text" required placeholder="e.g. 22CS501" class="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs font-mono-code uppercase text-slate-800 focus:outline-none focus:ring-2 focus:ring-brandBlue"/>
          </div>
          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">Academic Year *</label>
            <select id="up-academic-year" required class="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-brandBlue">
              <option value="2025-2026" selected>2025-2026</option>
              <option value="2024-2025">2024-2025</option>
              <option value="2023-2024">2023-2024</option>
              <option value="2022-2023">2022-2023</option>
              <option value="2021-2022">2021-2022</option>
              <option value="2020-2021">2020-2021</option>
            </select>
          </div>
        </div>

        <!-- Row 4: Subject Name -->
        <div>
          <label class="block text-xs font-semibold text-slate-700 mb-1">Subject Name *</label>
          <input id="up-subject-name" type="text" required placeholder="e.g. Operating Systems &amp; System Programming" class="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-brandBlue"/>
        </div>

        <!-- Row 5: IMAGE FILE UPLOAD -->
        <div>
          <label class="block text-xs font-semibold text-slate-700 mb-1">
            Question Paper Image / Document * <span class="text-slate-400 font-normal">(PNG, JPG, JPEG, WEBP, PDF up to 10MB)</span>
          </label>
          
          <div id="image-drop-area" class="border-2 border-dashed border-slate-300 hover:border-brandBlue rounded-2xl p-4 text-center cursor-pointer transition bg-slate-50/50 relative">
            <input type="file" id="up-image-file" accept="image/jpeg,image/png,image/webp,application/pdf" class="absolute inset-0 opacity-0 cursor-pointer w-full h-full" onchange="handleFileSelection(event)"/>
            
            <div id="drop-prompt" class="space-y-1.5 py-3">
              <i class="fa-solid fa-camera text-2xl text-slate-400"></i>
              <div class="text-xs font-semibold text-slate-700">Click to capture photo or select file</div>
              <p class="text-[11px] text-slate-400">Clear camera photo or scan of the question paper</p>
            </div>

            <!-- Image Selected Preview Thumbnail -->
            <div id="image-preview-container" style="display: none;" class="pt-2">
              <div class="relative inline-block max-w-full">
                <img id="image-preview" src="" alt="Selected Preview" class="max-h-48 rounded-xl mx-auto shadow border border-slate-200 object-contain"/>
                <div class="mt-2 flex items-center justify-center space-x-2">
                  <span id="image-filename" class="text-xs font-mono-code text-slate-700 font-bold truncate max-w-xs">file.jpg</span>
                  <span id="image-filesize" class="text-[11px] text-slate-400 font-mono-code">(0 KB)</span>
                  <button type="button" onclick="clearSelectedImage()" class="px-2 py-1 bg-red-100 text-red-700 rounded-lg text-[11px] font-bold hover:bg-red-200 transition">
                    <i class="fa-solid fa-trash-can text-[10px]"></i> Remove Image
                  </button>
                </div>
              </div>
            </div>
          </div>
          <p id="upload-image-error" style="display: none;" class="text-[11px] text-red-600 font-semibold mt-1">
            * Please attach a photo or image of the question paper.
          </p>
        </div>

        <!-- Buttons -->
        <div class="pt-3 flex items-center space-x-3">
          <button type="button" onclick="closeUploadModal()" class="flex-1 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-semibold transition">
            Cancel
          </button>
          <button type="submit" id="btn-submit-paper" class="flex-1 py-2.5 bg-brandBlue hover:bg-brandBlueHover text-white rounded-xl text-xs font-bold transition shadow-sm flex items-center justify-center space-x-1.5">
            <i class="fa-solid fa-cloud-arrow-up text-xs"></i>
            <span>Upload &amp; Publish Paper</span>
          </button>
        </div>

      </form>

    </div>
  </div>

  <!-- ================= 5. ADMIN MANAGEMENT & SUPABASE MODAL ================= -->
  <div id="admin-modal" style="display: none;" class="fixed inset-0 z-50 bg-slate-900/70 backdrop-blur-sm items-center justify-center p-4 overflow-y-auto">
    <div class="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200 relative my-6">
      <button type="button" onclick="closeAdminModal()" class="absolute top-4 right-4 text-slate-400 hover:text-slate-600 p-1">
        <i class="fa-solid fa-xmark text-base"></i>
      </button>

      <div class="text-center mb-5">
        <div class="w-12 h-12 bg-amber-50 text-amber-700 rounded-2xl flex items-center justify-center mx-auto mb-2 border border-amber-200">
          <i class="fa-solid fa-user-shield text-xl"></i>
        </div>
        <h3 class="text-base font-bold text-slate-900">Administrator &amp; Cloud Control</h3>
        <p class="text-xs text-slate-500 mt-0.5">Server-Side Supabase Authentication &amp; Moderation</p>
      </div>

      <!-- If Not Logged In As Admin -->
      <div id="admin-login-box">
        <form onsubmit="handleAdminLogin(event)" class="space-y-3">
          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">Administrator Email *</label>
            <input id="admin-email-input" type="email" required placeholder="admin@sru.edu.in" class="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-brandBlue"/>
          </div>
          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1">Administrator Password *</label>
            <input id="admin-password-input" type="password" required placeholder="Enter admin password" class="w-full px-3 py-2 bg-slate-50 border border-slate-300 rounded-xl text-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-brandBlue"/>
          </div>
          <button type="submit" id="admin-login-submit-btn" class="w-full py-2.5 bg-brandBlue hover:bg-brandBlueHover text-white rounded-xl text-xs font-bold transition shadow-sm">
            Sign In with Supabase Admin Auth
          </button>
        </form>
      </div>

      <!-- If Logged In As Admin -->
      <div id="admin-controls-box" style="display: none;" class="space-y-4">
        
        <div class="p-3 bg-emerald-50 rounded-xl border border-emerald-200 flex items-center justify-between">
          <div class="flex items-center space-x-2">
            <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
            <span class="text-xs font-bold text-emerald-900">Verified Administrator Session</span>
          </div>
          <button type="button" onclick="handleAdminSignOut()" class="text-[11px] text-red-600 hover:text-red-800 font-bold underline">
            Sign Out Admin
          </button>
        </div>

        <!-- Campus Announcement -->
        <div class="p-3.5 bg-slate-50 rounded-xl border border-slate-200">
          <label class="block text-xs font-bold text-slate-800 mb-1">
            <i class="fa-solid fa-bullhorn text-brandBlue mr-1"></i> Update Campus Announcement
          </label>
          <textarea id="admin-notice-input" rows="2" class="w-full p-2 bg-white border border-slate-300 rounded-lg text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-brandBlue mb-2"></textarea>
          <button type="button" onclick="saveAnnouncementFromModal()" class="w-full py-1.5 bg-slate-800 hover:bg-slate-900 text-white rounded-lg text-xs font-bold transition">
            Publish Notice to Dashboard
          </button>
        </div>

        <!-- Clear Archive -->
        <div class="p-3.5 bg-red-50 rounded-xl border border-red-200">
          <label class="block text-xs font-bold text-red-900 mb-0.5">
            <i class="fa-solid fa-triangle-exclamation text-red-600 mr-1"></i> Danger Zone
          </label>
          <p class="text-[11px] text-red-700 mb-2">Erase all question papers from database (requires Admin RLS policy).</p>
          <button type="button" onclick="adminClearAllPapers()" class="w-full py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-bold transition">
            Clear Entire Paper Archive
          </button>
        </div>

      </div>

    </div>
  </div>

  <!-- Toast Notification Container -->
  <div id="toast-container" class="fixed bottom-6 right-6 z-50 flex flex-col space-y-2 pointer-events-none"></div>

  <!-- ================= 6. JAVASCRIPT CONTROLLER ================= -->
  <script>
    // Global Application State (No Hardcoded Admin Credentials)
    let currentUser = null;
    let isAdmin = false;
    let isGuest = false;
    let papersList = [];
    let activeFilterBranch = 'ALL';
    let activePaperInViewer = null;
    let viewerZoomLevel = 1.0;
    let viewerRotationDeg = 0;
    let selectedImageBase64 = null;
    let selectedImageBlob = null;
    let selectedImageMime = 'image/webp';
    let selectedFileObj = null;
    let supabaseClient = null;

    // Initialize Supabase Client
    function initSupabase() {
      const url = window.SUPABASE_URL || 'https://dcjhszgcljkrvjdlnwhh.supabase.co';
      const key = window.SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRjamhzemdjbGprcnZqZGxud2hoIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTA5OTg4NjAsImV4cCI6MjEwNjU3NDg2MH0.jg8nPJueBUJmbv7KyQynyyVgmTsRWUC-ivu0L7sJdb4';

      if (url && key && window.supabase) {
        try {
          supabaseClient = window.supabase.createClient(url, key);
          updateCloudStatusUI(true);
          return true;
        } catch (err) {
          updateCloudStatusUI(false);
          return false;
        }
      } else {
        updateCloudStatusUI(false);
        return false;
      }
    }

    function updateCloudStatusUI(connected) {
      const authStatus = document.getElementById('auth-cloud-status');
      const navDot = document.getElementById('nav-cloud-dot');
      const navLabel = document.getElementById('nav-cloud-label');

      if (connected) {
        if (authStatus) authStatus.innerHTML = '<span class="w-2 h-2 rounded-full bg-emerald-500"></span> <span class="text-emerald-700 font-medium">Supabase Cloud Connected</span>';
        if (navDot) navDot.className = 'w-2 h-2 rounded-full bg-emerald-500';
        if (navLabel) navLabel.textContent = 'Supabase Cloud';
      } else {
        if (authStatus) authStatus.innerHTML = '<span class="w-2 h-2 rounded-full bg-blue-500"></span> <span class="text-blue-700 font-medium">Local Server Mode</span>';
        if (navDot) navDot.className = 'w-2 h-2 rounded-full bg-blue-500';
        if (navLabel) navLabel.textContent = 'Local Server';
      }
    }

    // Helper: Make Local API Calls (Development Fallback)
    async function apiCall(endpoint, method = 'GET', body = null) {
      try {
        const options = {
          method,
          headers: { 'Content-Type': 'application/json' }
        };
        if (body) {
          options.body = JSON.stringify(body);
        }
        const res = await fetch(endpoint, options);
        if (!res.ok) return null;
        return await res.json();
      } catch (err) {
        return null;
      }
    }

    // Initialization: Check active Supabase session or show login screen
    window.addEventListener('DOMContentLoaded', async () => {
      initSupabase();

      // Check for active Supabase Auth Session
      if (supabaseClient) {
        try {
          const { data: { session } } = await supabaseClient.auth.getSession();
          if (session && session.user) {
            await applyAuthenticatedUser(session.user);
            await initDashboard();
            return;
          }
        } catch(e) {}
      }

      showAuthView();
    });

    // Helper to populate user session and check server-side admin role
    async function applyAuthenticatedUser(user) {
      if (!user) return;

      let prof = null;
      if (supabaseClient) {
        try {
          const { data } = await supabaseClient.from('profiles').select('*').eq('id', user.id).maybeSingle();
          if (data) prof = data;
        } catch(e) {}
      }

      currentUser = {
        id: user.id,
        email: user.email,
        rollNo: prof?.roll_no || user.user_metadata?.roll_no || user.email?.split('@')[0]?.toUpperCase() || 'STUDENT',
        name: prof?.name || user.user_metadata?.name || 'Student',
        branch: prof?.branch || user.user_metadata?.branch || 'CSE',
        semester: prof?.semester || user.user_metadata?.semester || 1
      };
      isGuest = false;

      // Verify server-side admin privilege
      await checkAdminPrivilege(user.id);
    }

    async function checkAdminPrivilege(userId) {
      isAdmin = false;
      if (!supabaseClient || !userId) return;

      try {
        const { data: isAdminRpc } = await supabaseClient.rpc('is_admin');
        if (isAdminRpc === true) {
          isAdmin = true;
          return;
        }
        
        const { data: roleData } = await supabaseClient.from('admin_roles').select('role').eq('user_id', userId).maybeSingle();
        if (roleData && roleData.role === 'admin') {
          isAdmin = true;
        }
      } catch(e) {
        isAdmin = false;
      }
    }

    // Authentication Tabs (Sign In / Register)
    let currentAuthMode = 'login';
    function setAuthTab(mode) {
      currentAuthMode = mode;
      const tabLogin = document.getElementById('auth-tab-login');
      const tabRegister = document.getElementById('auth-tab-register');
      const fieldName = document.getElementById('field-name');
      const fieldRoll = document.getElementById('field-roll');
      const fieldBranch = document.getElementById('field-branch');
      const fieldSem = document.getElementById('field-sem');
      const submitBtn = document.getElementById('auth-submit-btn');

      if (mode === 'login') {
        tabLogin.className = "flex-1 pb-3 border-b-2 border-brandBlue text-brandBlue font-bold transition";
        tabRegister.className = "flex-1 pb-3 text-slate-400 hover:text-slate-600 transition";
        fieldName.style.display = 'none';
        fieldRoll.style.display = 'none';
        fieldBranch.style.display = 'none';
        fieldSem.style.display = 'none';
        submitBtn.innerHTML = '<span>Sign In to Dashboard</span> <i class="fa-solid fa-arrow-right text-xs"></i>';
      } else {
        tabRegister.className = "flex-1 pb-3 border-b-2 border-brandBlue text-brandBlue font-bold transition";
        tabLogin.className = "flex-1 pb-3 text-slate-400 hover:text-slate-600 transition";
        fieldName.style.display = 'block';
        fieldRoll.style.display = 'block';
        fieldBranch.style.display = 'block';
        fieldSem.style.display = 'block';
        submitBtn.innerHTML = '<span>Register &amp; Continue</span> <i class="fa-solid fa-arrow-right text-xs"></i>';
      }
    }

    // Handle Student Authentication (Supabase Auth SignUp / SignIn)
    async function handleAuthSubmit(event) {
      event.preventDefault();
      const email = document.getElementById('login-email').value.trim().toLowerCase();
      const password = document.getElementById('login-password').value;
      const submitBtn = document.getElementById('auth-submit-btn');

      if (!email || !password) {
        alert('Please enter both your email address and password.');
        return;
      }

      submitBtn.disabled = true;
      submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> <span>Authenticating...</span>';

      if (currentAuthMode === 'register') {
        const name = document.getElementById('login-name').value.trim() || 'Student';
        const rollNo = (document.getElementById('login-roll').value.trim() || 'STUDENT').toUpperCase();
        const branch = document.getElementById('login-branch').value;
        const semester = parseInt(document.getElementById('login-sem').value) || 1;

        if (password.length < 6) {
          alert('Password must be at least 6 characters long.');
          submitBtn.disabled = false;
          submitBtn.innerHTML = '<span>Register &amp; Continue</span> <i class="fa-solid fa-arrow-right text-xs"></i>';
          return;
        }

        if (supabaseClient) {
          try {
            const { data, error } = await supabaseClient.auth.signUp({
              email,
              password,
              options: {
                data: { roll_no: rollNo, name, branch, semester }
              }
            });

            if (error) {
              alert('Registration failed: ' + error.message);
              submitBtn.disabled = false;
              submitBtn.innerHTML = '<span>Register &amp; Continue</span> <i class="fa-solid fa-arrow-right text-xs"></i>';
              return;
            }

            if (data && data.user) {
              await applyAuthenticatedUser(data.user);
              showToast('Registered and authenticated successfully!', 'success');
              initDashboard();
              return;
            }
          } catch(err) {
            alert('Registration error: ' + err.message);
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<span>Register &amp; Continue</span> <i class="fa-solid fa-arrow-right text-xs"></i>';
            return;
          }
        }
      } else {
        // Student Sign In
        if (supabaseClient) {
          try {
            const { data, error } = await supabaseClient.auth.signInWithPassword({
              email,
              password
            });

            if (error) {
              alert('Sign In failed: ' + error.message);
              submitBtn.disabled = false;
              submitBtn.innerHTML = '<span>Sign In to Dashboard</span> <i class="fa-solid fa-arrow-right text-xs"></i>';
              return;
            }

            if (data && data.user) {
              await applyAuthenticatedUser(data.user);
              showToast('Signed in successfully!', 'success');
              initDashboard();
              return;
            }
          } catch(err) {
            alert('Sign In error: ' + err.message);
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<span>Sign In to Dashboard</span> <i class="fa-solid fa-arrow-right text-xs"></i>';
            return;
          }
        }
      }

      submitBtn.disabled = false;
    }

    // Guest Mode (Read-Only Search & Paper Viewing)
    function continueAsGuest() {
      currentUser = {
        id: null,
        rollNo: 'GUEST',
        name: 'Guest Student',
        email: 'guest@sru.edu.in',
        branch: 'CSE',
        semester: 1
      };
      isGuest = true;
      isAdmin = false;
      showToast('Browsing in Guest Mode (Read-Only)', 'info');
      initDashboard();
    }

    // Secure Admin Modal Controllers
    function openAdminModal() {
      document.getElementById('admin-modal').style.display = 'flex';
      if (isAdmin) {
        document.getElementById('admin-login-box').style.display = 'none';
        document.getElementById('admin-controls-box').style.display = 'block';
        document.getElementById('admin-notice-input').value = document.getElementById('announcement-text').textContent;
      } else {
        document.getElementById('admin-login-box').style.display = 'block';
        document.getElementById('admin-controls-box').style.display = 'none';
        document.getElementById('admin-password-input').value = '';
      }
    }

    function closeAdminModal() {
      document.getElementById('admin-modal').style.display = 'none';
    }

    // Secure Admin Sign-In using Supabase Auth
    async function handleAdminLogin(event) {
      event.preventDefault();
      const email = document.getElementById('admin-email-input').value.trim();
      const password = document.getElementById('admin-password-input').value;
      const submitBtn = document.getElementById('admin-login-submit-btn');

      if (!email || !password) {
        alert('Please enter your administrator email and password.');
        return;
      }

      submitBtn.disabled = true;
      submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> <span>Verifying Admin Privileges...</span>';

      if (supabaseClient) {
        try {
          const { data, error } = await supabaseClient.auth.signInWithPassword({
            email,
            password
          });

          if (error) {
            alert('Authentication failed: ' + error.message);
            submitBtn.disabled = false;
            submitBtn.innerHTML = 'Sign In with Supabase Admin Auth';
            return;
          }

          if (data && data.user) {
            await checkAdminPrivilege(data.user.id);
            if (isAdmin) {
              await applyAuthenticatedUser(data.user);
              showToast('Admin session verified via database role policy', 'success');
              openAdminModal();
              initDashboard();
            } else {
              alert('Access Denied: Your account is authenticated, but your user ID is not registered in the public.admin_roles table.');
              await supabaseClient.auth.signOut();
            }
          }
        } catch(err) {
          alert('Admin login error: ' + err.message);
        }
      } else {
        alert('Supabase client is not connected. Admin actions require cloud database connection.');
      }

      submitBtn.disabled = false;
      submitBtn.innerHTML = 'Sign In with Supabase Admin Auth';
    }

    async function handleAdminSignOut() {
      if (supabaseClient) {
        await supabaseClient.auth.signOut();
      }
      isAdmin = false;
      currentUser = null;
      closeAdminModal();
      showAuthView();
      showToast('Admin signed out', 'info');
    }

    // Admin Actions (Secured by Database RLS)
    async function saveAnnouncementFromModal() {
      const text = document.getElementById('admin-notice-input').value.trim();
      if (!text) return;

      if (!isAdmin || !supabaseClient) {
        alert('Unauthorized: Administrator authorization required.');
        return;
      }

      try {
        const { error } = await supabaseClient.from('announcements').upsert({ id: 1, text, updated_at: new Date() });
        if (error) {
          alert('Failed to update announcement: ' + error.message);
          return;
        }
        document.getElementById('announcement-text').textContent = text;
        showToast('Announcement published live to all students!', 'success');
      } catch(e) {
        alert('Error updating notice: ' + e.message);
      }
    }

    async function adminDeletePaper(paperId, event) {
      if (event) event.stopPropagation();
      if (!confirm('Are you sure you want to permanently delete this question paper?')) {
        return;
      }

      if (supabaseClient) {
        const { error } = await supabaseClient.from('papers').delete().eq('id', paperId);
        if (error) {
          alert('Delete rejected by database policy: ' + error.message);
          return;
        }
        showToast('Question paper deleted', 'info');
        await fetchPapers();
      }
    }

    async function adminClearAllPapers() {
      if (!confirm('ADMIN ACTION: Are you sure you want to erase ALL uploaded papers from all branches?')) {
        return;
      }

      if (supabaseClient) {
        const { error } = await supabaseClient.from('papers').delete().neq('id', 'dummy_keep');
        if (error) {
          alert('Clear archive rejected by database policy: ' + error.message);
          return;
        }
        showToast('All question papers have been cleared', 'info');
        await fetchPapers();
      }
    }

    async function editAnnouncementPrompt() {
      openAdminModal();
    }

    async function handleLogout() {
      if (supabaseClient) {
        try {
          await supabaseClient.auth.signOut();
        } catch(e) {}
      }
      currentUser = null;
      isAdmin = false;
      isGuest = false;
      showAuthView();
      showToast('Signed out of PaperHub', 'info');
    }

    function showAuthView() {
      document.getElementById('auth-view').style.display = 'flex';
      document.getElementById('app-view').style.display = 'none';
      closeUploadModal();
      closeViewerModal();
    }

    function showDashboardView() {
      document.getElementById('auth-view').style.display = 'none';
      document.getElementById('app-view').style.display = 'flex';
    }

    async function initDashboard() {
      showDashboardView();

      // UI adjustments
      if (isAdmin) {
        document.getElementById('admin-badge').style.display = 'flex';
        document.getElementById('btn-admin-clear').style.display = 'flex';
        document.getElementById('btn-edit-announcement').style.display = 'inline-flex';
        document.getElementById('nav-student-roll').textContent = 'ADMIN';
        document.getElementById('nav-student-branch').textContent = 'System Admin';
        document.getElementById('welcome-heading').textContent = 'Administrator Control Panel';
        document.getElementById('welcome-subheading').textContent = 'Manage university papers archive, moderate uploaded student submissions, and update announcements.';
      } else if (isGuest) {
        document.getElementById('admin-badge').style.display = 'none';
        document.getElementById('btn-admin-clear').style.display = 'none';
        document.getElementById('btn-edit-announcement').style.display = 'none';
        document.getElementById('nav-student-roll').textContent = 'GUEST';
        document.getElementById('nav-student-branch').textContent = 'Read-Only Mode';
        document.getElementById('welcome-heading').textContent = 'Welcome, Guest Student';
        document.getElementById('welcome-subheading').textContent = 'Browse and search past exam papers across all regulations. Sign in to upload new question papers.';
      } else {
        document.getElementById('admin-badge').style.display = 'none';
        document.getElementById('btn-admin-clear').style.display = 'none';
        document.getElementById('btn-edit-announcement').style.display = 'none';
        if (currentUser) {
          document.getElementById('nav-student-roll').textContent = currentUser.rollNo || 'Student';
          document.getElementById('nav-student-branch').textContent = `${currentUser.branch || 'CSE'} • Sem ${currentUser.semester || 1}`;
          document.getElementById('welcome-heading').textContent = `Welcome, ${currentUser.name || 'Student'} (${currentUser.rollNo || ''})`;
          document.getElementById('welcome-subheading').textContent = `Department of ${getBranchFullName(currentUser.branch)} • Semester ${currentUser.semester}. Browse past exam papers or upload newly scanned papers.`;
        }
      }

      // Fetch latest announcement
      if (supabaseClient) {
        try {
          const { data } = await supabaseClient.from('announcements').select('text').eq('id', 1).maybeSingle();
          if (data && data.text) {
            document.getElementById('announcement-text').textContent = data.text;
          }
        } catch(e) {}
      }

      await fetchPapers();
    }

    function getBranchFullName(code) {
      const map = {
        'CSE': 'Computer Science & Engineering',
        'AIML': 'Artificial Intelligence & Machine Learning',
        'AIDS': 'AI & Data Science',
        'ECE': 'Electronics & Communication Engineering',
        'EEE': 'Electrical & Electronics Engineering',
        'MECH': 'Mechanical Engineering',
        'CIVIL': 'Civil Engineering'
      };
      return map[code] || code;
    }

    // Fetch papers from Supabase
    async function fetchPapers() {
      let loaded = false;

      if (supabaseClient) {
        try {
          const { data, error } = await supabaseClient
            .from('papers')
            .select('*')
            .order('created_at', { ascending: false });

          if (!error && Array.isArray(data)) {
            papersList = data.map(row => ({
              id: row.id,
              userId: row.user_id,
              subjectCode: row.subject_code,
              subjectName: row.subject_name,
              branch: row.branch,
              semester: row.semester,
              examType: row.exam_type,
              examTypeLabel: row.exam_type_label || (row.exam_type === 'MID_1' ? 'Mid-Term 1' : (row.exam_type === 'MID_2' ? 'Mid-Term 2' : 'Semester End')),
              regulation: row.regulation,
              academicYear: row.academic_year,
              duration: row.duration,
              maxMarks: row.max_marks,
              uploaderName: row.uploader_name,
              uploaderRollNo: row.uploader_roll,
              imageUrl: row.image_url,
              downloadCount: row.download_count || 0
            }));
            loaded = true;
          }
        } catch (err) {
          papersList = [];
        }
      }

      renderPapers();
      updateMetrics();
    }

    function updateMetrics() {
      const total = papersList.length;
      const branchCount = papersList.filter(p => currentUser && p.branch && p.branch.toUpperCase() === currentUser.branch.toUpperCase()).length;
      const totalDownloads = papersList.reduce((acc, p) => acc + (p.downloadCount || 0), 0);

      document.getElementById('stat-total-papers').textContent = total;
      document.getElementById('stat-branch-papers').textContent = branchCount;
      document.getElementById('stat-branch-label').textContent = currentUser && currentUser.branch ? `For ${currentUser.branch} Branch` : 'For your branch';
      document.getElementById('stat-total-downloads').textContent = totalDownloads;
    }

    function setBranchFilter(branch) {
      activeFilterBranch = branch;
      document.querySelectorAll('.branch-chip').forEach(btn => {
        btn.className = "branch-chip px-3 py-1.5 rounded-lg font-medium text-xs bg-slate-100 text-slate-600 hover:bg-slate-200 transition";
      });
      const activeBtn = document.getElementById(`branch-chip-${branch}`);
      if (activeBtn) {
        activeBtn.className = "branch-chip px-3 py-1.5 rounded-lg font-medium text-xs bg-brandBlue text-white shadow-sm transition";
      }
      renderPapers();
    }

    function handleSearchFilter() {
      renderPapers();
    }

    function focusSearch() {
      const input = document.getElementById('search-query');
      if (input) {
        input.focus();
        input.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }

    // Render Question Papers Cards with XSS protection
    function renderPapers() {
      const query = (document.getElementById('search-query')?.value || '').toLowerCase().trim();
      const semFilter = document.getElementById('filter-semester')?.value || 'ALL';
      const examFilter = document.getElementById('filter-exam-type')?.value || 'ALL';
      const regFilter = document.getElementById('filter-regulation')?.value || 'ALL';
      const yearFilter = document.getElementById('filter-academic-year')?.value || 'ALL';

      let filtered = papersList.filter(paper => {
        if (activeFilterBranch !== 'ALL' && paper.branch && paper.branch.toUpperCase() !== activeFilterBranch.toUpperCase()) {
          return false;
        }
        if (semFilter !== 'ALL' && String(paper.semester) !== String(semFilter)) {
          return false;
        }
        if (examFilter !== 'ALL' && paper.examType && paper.examType.toUpperCase() !== examFilter.toUpperCase()) {
          return false;
        }
        if (regFilter !== 'ALL' && paper.regulation && paper.regulation.toUpperCase() !== regFilter.toUpperCase()) {
          return false;
        }
        if (yearFilter !== 'ALL' && paper.academicYear && paper.academicYear !== yearFilter) {
          return false;
        }
        if (query) {
          const matchCode = (paper.subjectCode || '').toLowerCase().includes(query);
          const matchName = (paper.subjectName || '').toLowerCase().includes(query);
          const matchBranch = (paper.branch || '').toLowerCase().includes(query);
          const matchYear = (paper.academicYear || '').toLowerCase().includes(query);
          if (!matchCode && !matchName && !matchBranch && !matchYear) {
            return false;
          }
        }
        return true;
      });

      const grid = document.getElementById('papers-grid');
      const emptyState = document.getElementById('empty-state');
      const countBadge = document.getElementById('papers-count-badge');

      countBadge.textContent = `${filtered.length} paper${filtered.length === 1 ? '' : 's'} available`;

      if (filtered.length === 0) {
        grid.innerHTML = '';
        emptyState.style.display = 'block';
        return;
      }

      emptyState.style.display = 'none';
      grid.innerHTML = filtered.map(paper => createPaperCardHTML(paper)).join('');
    }

    // Paper Card HTML Builder with Strict Sanitization
    function createPaperCardHTML(paper) {
      const examLabel = paper.examTypeLabel || (paper.examType === 'MID_1' ? 'Mid-Term 1' : (paper.examType === 'MID_2' ? 'Mid-Term 2' : 'Semester End'));
      const thumbnailSrc = sanitizeUrl(paper.imageUrl);
      const isOwner = currentUser && currentUser.id && paper.userId && currentUser.id === paper.userId;
      const canDelete = isAdmin || isOwner;

      return `
        <div class="bg-white rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition duration-200 flex flex-col overflow-hidden group">
          <!-- Card Header Badges -->
          <div class="p-4 pb-3 border-b border-slate-100 flex items-center justify-between">
            <div class="flex items-center space-x-2">
              <span class="font-mono-code text-xs font-bold px-2.5 py-1 bg-blue-50 text-brandBlue rounded-lg border border-blue-200">
                ${escapeHTML(paper.subjectCode)}
              </span>
              <span class="text-[11px] font-semibold text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
                ${escapeHTML(paper.regulation || 'R22')}
              </span>
            </div>
            <span class="text-[11px] font-semibold text-brandBlueDark bg-blue-100/60 px-2.5 py-0.5 rounded-full">
              ${escapeHTML(examLabel)}
            </span>
          </div>

          <!-- Subject Title & Branch Info -->
          <div class="p-4 flex-1">
            <h4 class="text-sm font-bold text-slate-900 group-hover:text-brandBlue transition leading-snug line-clamp-2">
              ${escapeHTML(paper.subjectName)}
            </h4>
            <div class="mt-1.5 flex items-center space-x-2 text-xs text-slate-500">
              <span class="font-semibold text-slate-700">${escapeHTML(paper.branch)}</span>
              <span>•</span>
              <span>Semester ${parseInt(paper.semester) || 1}</span>
              <span>•</span>
              <span>${escapeHTML(paper.academicYear || '2025-2026')}</span>
            </div>

            <!-- Image Thumbnail Preview -->
            <div onclick="openViewerModal('${escapeHTML(paper.id)}')" class="mt-3.5 relative bg-slate-50 border border-slate-200 rounded-xl overflow-hidden cursor-pointer h-40 flex items-center justify-center group/img">
              <img src="${thumbnailSrc}" alt="Paper Thumbnail" class="w-full h-full object-cover object-top opacity-90 group-hover/img:opacity-100 transition"/>
              <div class="absolute inset-0 bg-blue-950/20 group-hover/img:bg-blue-950/40 flex items-center justify-center transition">
                <span class="px-3 py-1.5 bg-white text-brandBlueDark text-xs font-bold rounded-lg shadow flex items-center space-x-1.5 group-hover/img:scale-105 transition">
                  <i class="fa-solid fa-eye text-xs"></i>
                  <span>View Paper Image</span>
                </span>
              </div>
            </div>

            <!-- Contributor info (Privacy Protected) -->
            <div class="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
              <span class="truncate font-mono-code">By ${escapeHTML(paper.uploaderRollNo || 'Student')}</span>
              <span class="font-mono-code text-slate-400">${parseInt(paper.downloadCount) || 0} downloads</span>
            </div>
          </div>

          <!-- Card Actions -->
          <div class="px-4 py-3 bg-slate-50 border-t border-slate-100 flex items-center space-x-2">
            <button type="button" onclick="openViewerModal('${escapeHTML(paper.id)}')" class="flex-1 py-2 bg-brandBlue hover:bg-brandBlueHover text-white rounded-xl text-xs font-bold shadow-sm transition flex items-center justify-center space-x-1.5">
              <i class="fa-solid fa-magnifying-glass text-xs"></i>
              <span>View Full Paper</span>
            </button>
            <a href="${thumbnailSrc}" download="${escapeHTML(paper.subjectCode)}_${escapeHTML(paper.branch)}_${escapeHTML(paper.examType)}.png" target="_blank" onclick="trackDownload('${escapeHTML(paper.id)}')" class="p-2 bg-white hover:bg-blue-50 text-slate-700 hover:text-brandBlue border border-slate-300 rounded-xl transition" title="Direct Download Image">
              <i class="fa-solid fa-arrow-down text-xs"></i>
            </a>
            ${canDelete ? `
              <button type="button" onclick="adminDeletePaper('${escapeHTML(paper.id)}', event)" class="p-2 bg-red-50 hover:bg-red-100 text-red-600 rounded-xl transition border border-red-200" title="Delete Paper">
                <i class="fa-solid fa-trash-can text-xs"></i>
              </button>
            ` : ''}
          </div>
        </div>
      `;
    }

    // Question Paper Image Viewer Controller
    function openViewerModal(paperId) {
      const paper = papersList.find(p => p.id === paperId);
      if (!paper) return;

      activePaperInViewer = paper;
      viewerZoomLevel = 1.0;
      viewerRotationDeg = 0;

      document.getElementById('viewer-subject-code').textContent = paper.subjectCode;
      document.getElementById('viewer-subject-name').textContent = paper.subjectName;
      document.getElementById('viewer-meta').textContent = `${paper.branch} • Semester ${paper.semester} • ${paper.examTypeLabel || paper.examType} (${paper.regulation || 'R22'}) • ${paper.academicYear || '2025-2026'}`;
      document.getElementById('viewer-uploader').textContent = paper.uploaderRollNo ? `Enrollment: ${paper.uploaderRollNo}` : 'SRU Student';
      document.getElementById('viewer-year').textContent = paper.academicYear || '2025-2026';
      document.getElementById('viewer-marks').textContent = `${paper.maxMarks || 30} Marks (${paper.duration || '90 Mins'})`;

      const viewerImg = document.getElementById('viewer-image');
      viewerImg.src = sanitizeUrl(paper.imageUrl);
      viewerImg.style.transform = 'scale(1) rotate(0deg)';

      document.getElementById('viewer-modal').style.display = 'flex';
      document.body.classList.add('overflow-hidden');
    }

    function closeViewerModal() {
      document.getElementById('viewer-modal').style.display = 'none';
      document.body.classList.remove('overflow-hidden');
      activePaperInViewer = null;
    }

    function zoomViewer(delta) {
      viewerZoomLevel = Math.max(0.5, Math.min(3.5, viewerZoomLevel + delta));
      applyViewerTransform();
    }

    function rotateViewer() {
      viewerRotationDeg = (viewerRotationDeg + 90) % 360;
      applyViewerTransform();
    }

    function applyViewerTransform() {
      const img = document.getElementById('viewer-image');
      if (img) {
        img.style.transform = `scale(${viewerZoomLevel}) rotate(${viewerRotationDeg}deg)`;
      }
    }

    function downloadActivePaperImage() {
      if (!activePaperInViewer) return;
      trackDownload(activePaperInViewer.id);
      const link = document.createElement('a');
      link.href = sanitizeUrl(activePaperInViewer.imageUrl);
      link.download = `${activePaperInViewer.subjectCode}_${activePaperInViewer.branch}_${activePaperInViewer.examType}.png`;
      link.target = '_blank';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }

    async function trackDownload(paperId) {
      const p = papersList.find(item => item.id === paperId);
      if (p) {
        p.downloadCount = (p.downloadCount || 0) + 1;
        updateMetrics();
        if (supabaseClient) {
          try {
            await supabaseClient.rpc('increment_download', { paper_id: paperId });
          } catch(e) {}
        }
      }
    }

    // Image Upload Modal Controller
    function openUploadModal() {
      if (isGuest || !currentUser || !currentUser.id) {
        alert('Please sign in or register with your college account to upload question papers.');
        showAuthView();
        return;
      }

      if (currentUser && currentUser.branch) {
        document.getElementById('up-branch').value = currentUser.branch;
        document.getElementById('up-semester').value = currentUser.semester;
      }
      clearSelectedImage();
      document.getElementById('upload-modal').style.display = 'flex';
      document.body.classList.add('overflow-hidden');
    }

    function closeUploadModal() {
      document.getElementById('upload-modal').style.display = 'none';
      document.body.classList.remove('overflow-hidden');
      document.getElementById('paper-upload-form').reset();
      clearSelectedImage();
    }

    // High-Performance In-Browser Image Optimization (WebP/JPEG Adaptive Compression)
    async function compressImageFile(file, maxDim = 1600, quality = 0.82) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => {
          const img = new Image();
          img.onload = () => {
            let w = img.width;
            let h = img.height;
            if (w > maxDim || h > maxDim) {
              if (w > h) {
                h = Math.round((h * maxDim) / w);
                w = maxDim;
              } else {
                w = Math.round((w * maxDim) / h);
                w = maxDim;
              }
            }
            const canvas = document.createElement('canvas');
            canvas.width = w;
            canvas.height = h;
            const ctx = canvas.getContext('2d');
            ctx.imageSmoothingEnabled = true;
            ctx.imageSmoothingQuality = 'high';
            ctx.drawImage(img, 0, 0, w, h);

            // Prefer WebP for max compression + clarity, fallback to JPEG
            let mime = 'image/webp';
            let dataUrl = canvas.toDataURL(mime, quality);
            if (!dataUrl.startsWith('data:image/webp')) {
              mime = 'image/jpeg';
              dataUrl = canvas.toDataURL(mime, quality);
            }

            canvas.toBlob((blob) => {
              if (!blob) {
                const parts = dataUrl.split(',');
                const byteCharacters = atob(parts[1]);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) {
                  byteNumbers[i] = byteCharacters.charCodeAt(i);
                }
                blob = new Blob([new Uint8Array(byteNumbers)], { type: mime });
              }
              resolve({
                blob: blob,
                dataUrl: dataUrl,
                mime: mime,
                width: w,
                height: h,
                originalSize: file.size,
                compressedSize: blob.size
              });
            }, mime, quality);
          };
          img.onerror = () => reject(new Error('Failed to load image for compression'));
          img.src = e.target.result;
        };
        reader.onerror = () => reject(new Error('Failed to read file'));
        reader.readAsDataURL(file);
      });
    }

    // File Selection & Security Hardening
    async function handleFileSelection(event) {
      const file = event.target.files && event.target.files[0];
      if (!file) return;

      // File Size Check (Max 15 MB)
      const MAX_SIZE = 15 * 1024 * 1024;
      if (file.size > MAX_SIZE) {
        alert('File size exceeds the 15MB limit. Please upload a smaller image.');
        clearSelectedImage();
        return;
      }

      // Strict MIME and Extension Whitelist (Block SVG, HTML, JS, EXE, scripts)
      const allowedMimes = ['image/jpeg', 'image/png', 'image/webp', 'application/pdf'];
      const fileExt = file.name.split('.').pop().toLowerCase();
      const allowedExts = ['jpg', 'jpeg', 'png', 'webp', 'pdf'];

      if (!allowedMimes.includes(file.type) || !allowedExts.includes(fileExt)) {
        alert('Security Alert: Only JPG, PNG, WEBP, and PDF documents are allowed. Executable and SVG files are rejected.');
        clearSelectedImage();
        return;
      }

      selectedFileObj = file;
      document.getElementById('upload-image-error').style.display = 'none';

      if (file.type.startsWith('image/')) {
        try {
          document.getElementById('drop-prompt').innerHTML = '<div class="py-3"><i class="fa-solid fa-spinner fa-spin text-2xl text-brandBlue"></i><p class="text-xs font-semibold text-slate-700 mt-2">Optimizing &amp; compressing image...</p></div>';
          
          const result = await compressImageFile(file, 1600, 0.82);
          selectedImageBlob = result.blob;
          selectedImageBase64 = result.dataUrl;
          selectedImageMime = result.mime;

          showOptimizedPreview(file.name, result.originalSize, result.compressedSize, result.dataUrl, false);
        } catch (err) {
          console.error('Compression error:', err);
          const reader = new FileReader();
          reader.onload = (e) => {
            selectedImageBase64 = e.target.result;
            selectedImageBlob = file;
            selectedImageMime = file.type;
            showOptimizedPreview(file.name, file.size, file.size, selectedImageBase64, false);
          };
          reader.readAsDataURL(file);
        }
      } else {
        // PDF document
        selectedImageBlob = file;
        selectedImageMime = 'application/pdf';
        const reader = new FileReader();
        reader.onload = (e) => {
          selectedImageBase64 = e.target.result;
          showOptimizedPreview(file.name, file.size, file.size, '/images/paper_dsa.svg', true);
        };
        reader.readAsDataURL(file);
      }
    }

    function showOptimizedPreview(name, origSize, compSize, src, isPdf = false) {
      document.getElementById('drop-prompt').style.display = 'none';
      const previewContainer = document.getElementById('image-preview-container');
      previewContainer.style.display = 'block';
      document.getElementById('image-preview').src = src;
      document.getElementById('image-filename').textContent = name;

      const origKB = Math.round(origSize / 1024);
      const compKB = Math.round(compSize / 1024);
      const savings = origSize > compSize ? Math.round(((origSize - compSize) / origSize) * 100) : 0;

      const sizeBadge = document.getElementById('image-filesize');
      if (!isPdf && savings > 10) {
        sizeBadge.innerHTML = `<span class="text-emerald-700 font-bold bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">✨ ${compKB} KB (Saved ${savings}%)</span> <span class="text-slate-400 line-through text-[10px]">(${origKB} KB)</span>`;
      } else {
        sizeBadge.textContent = `(${compKB} KB)`;
      }
    }

    function clearSelectedImage() {
      selectedImageBase64 = null;
      selectedImageBlob = null;
      selectedImageMime = 'image/webp';
      selectedFileObj = null;
      document.getElementById('up-image-file').value = '';
      document.getElementById('drop-prompt').innerHTML = '<i class="fa-solid fa-camera text-2xl text-slate-400"></i><div class="text-xs font-semibold text-slate-700">Click to capture photo or select file</div><p class="text-[11px] text-slate-400">Clear camera photo or scan of the question paper</p>';
      document.getElementById('drop-prompt').style.display = 'block';
      document.getElementById('image-preview-container').style.display = 'none';
      document.getElementById('image-preview').src = '';
    }

    // Submit Paper - Uploads to Supabase Cloud with Server-Side Verification
    async function handlePaperUploadSubmit(event) {
      event.preventDefault();

      if (!currentUser || !currentUser.id) {
        alert('Authentication required: Please sign in to upload question papers.');
        return;
      }

      if (!selectedImageBase64) {
        document.getElementById('upload-image-error').style.display = 'block';
        return;
      }
      
      const submitBtn = document.getElementById('btn-submit-paper');
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> <span>Uploading to Supabase Cloud...</span>';

      const code = document.getElementById('up-subject-code').value.trim().toUpperCase();
      const name = document.getElementById('up-subject-name').value.trim();
      const branch = document.getElementById('up-branch').value;
      const sem = parseInt(document.getElementById('up-semester').value);
      const exam = document.getElementById('up-exam-type').value;
      const reg = document.getElementById('up-regulation').value;
      const year = document.getElementById('up-academic-year').value;

      // Input Validation
      if (code.length < 2 || code.length > 25) {
        alert('Subject code must be between 2 and 25 characters.');
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fa-solid fa-cloud-arrow-up text-xs"></i> <span>Upload &amp; Publish Paper</span>';
        return;
      }

      if (name.length < 2 || name.length > 150) {
        alert('Subject name must be between 2 and 150 characters.');
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fa-solid fa-cloud-arrow-up text-xs"></i> <span>Upload &amp; Publish Paper</span>';
        return;
      }

      const paperId = `sru_${branch.toLowerCase()}_${code.toLowerCase()}_${Date.now()}`;
      const examLabels = {
        'MID_1': 'Mid-Term 1',
        'MID_2': 'Mid-Term 2',
        'SEM_END': 'Semester End Exam',
        'SUPPLY': 'Supplementary Exam'
      };

      let uploadedImageUrl = null;
      let cloudSaved = false;
      let cloudErrorDetail = "";

      if (supabaseClient) {
        try {
          // Convert base64 to pure in-memory Blob
          let blob = selectedImageBlob;
          if (!blob && selectedImageBase64) {
            try {
              const parts = selectedImageBase64.split(',');
              const mimeMatch = parts[0].match(/:(.*?);/);
              const mimeType = mimeMatch ? mimeMatch[1] : 'image/webp';
              const byteCharacters = atob(parts[1]);
              const byteArrays = [];
              const sliceSize = 1024;
              for (let offset = 0; offset < byteCharacters.length; offset += sliceSize) {
                const slice = byteCharacters.slice(offset, offset + sliceSize);
                const byteNumbers = new Array(slice.length);
                for (let i = 0; i < slice.length; i++) {
                  byteNumbers[i] = slice.charCodeAt(i);
                }
                byteArrays.push(new Uint8Array(byteNumbers));
              }
              blob = new Blob(byteArrays, { type: mimeType });
            } catch(convErr) {
              const res = await fetch(selectedImageBase64);
              blob = await res.blob();
            }
          }

          // Determine safe extension from optimized blob type
          let ext = 'webp';
          if (blob && blob.type) {
            if (blob.type === 'image/jpeg') ext = 'jpg';
            else if (blob.type === 'image/png') ext = 'png';
            else if (blob.type === 'application/pdf') ext = 'pdf';
            else if (blob.type === 'image/webp') ext = 'webp';
          }
          const safeFileName = `${crypto.randomUUID()}.${ext}`;
          
          // Secure User-Scoped Storage Path: paper-images/{user_id}/{safeFileName}
          const storagePath = `${currentUser.id}/${safeFileName}`;

          // Upload to Supabase Storage Bucket 'paper-images'
          const { data: storageData, error: storageErr } = await supabaseClient
            .storage
            .from('paper-images')
            .upload(storagePath, blob, { contentType: blob ? blob.type : 'image/webp', upsert: false });

          if (!storageErr) {
            const { data: urlData } = supabaseClient.storage.from('paper-images').getPublicUrl(storagePath);
            uploadedImageUrl = urlData.publicUrl;
          } else {
            cloudErrorDetail += `Storage: ${storageErr.message || JSON.stringify(storageErr)}. `;
          }

          // Insert into Supabase 'papers' table with authenticated user_id
          const { error: dbErr } = await supabaseClient.from('papers').insert({
            id: paperId,
            user_id: currentUser.id,
            subject_code: code,
            subject_name: name,
            branch: branch,
            semester: sem,
            exam_type: exam,
            exam_type_label: examLabels[exam] || exam,
            regulation: reg,
            academic_year: year,
            duration: exam.includes('MID') ? '90 Mins' : '3 Hours',
            max_marks: exam.includes('MID') ? 30 : 60,
            uploader_name: currentUser.name || 'Student',
            uploader_roll: currentUser.rollNo || 'SRU',
            image_url: uploadedImageUrl || selectedImageBase64,
            download_count: 0
          });

          if (!dbErr) {
            cloudSaved = true;
          } else {
            cloudErrorDetail += `Database: ${dbErr.message || JSON.stringify(dbErr)}. `;
          }
        } catch (err) {
          cloudErrorDetail += `Connection: ${err.message || err}. `;
        }
      }

      submitBtn.disabled = false;
      submitBtn.innerHTML = '<i class="fa-solid fa-cloud-arrow-up text-xs"></i> <span>Upload &amp; Publish Paper</span>';

      if (cloudSaved) {
        showToast('Question paper uploaded successfully and published to all students!', 'success');
        closeUploadModal();
        await fetchPapers();
      } else {
        const errorMsg = cloudErrorDetail 
          ? `Upload failed: ${cloudErrorDetail}`
          : 'Upload failed. Please verify your internet connection and authentication.';
        alert(errorMsg);
      }
    }

    // Helper: Toast Notifications
    function showToast(message, type = 'info') {
      const container = document.getElementById('toast-container');
      const toast = document.createElement('div');
      
      const icon = type === 'success' ? 'fa-circle-check text-brandBlue' : 'fa-circle-info text-blue-600';
      toast.className = 'px-4 py-3 bg-white text-slate-800 rounded-xl shadow-lg border border-slate-200 text-xs font-semibold flex items-center space-x-2.5 transition-all duration-300 pointer-events-auto';
      toast.innerHTML = `
        <i class="fa-solid ${icon} text-sm"></i>
        <span>${escapeHTML(message)}</span>
      `;
      container.appendChild(toast);

      setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
      }, 3500);
    }

    // Helper: HTML Escaper (XSS Protection)
    function escapeHTML(str) {
      if (!str && str !== 0) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    // Helper: URL Sanitizer (Blocks javascript: and dangerous URI schemes)
    function sanitizeUrl(url) {
      if (!url) return '/images/paper_dsa.svg';
      const clean = String(url).trim();
      const lower = clean.toLowerCase();
      if (lower.startsWith('javascript:') || lower.startsWith('vbscript:') || lower.startsWith('data:text/html')) {
        return '/images/paper_dsa.svg';
      }
      return clean;
    }
  </script>
</body>
</html>
'''

with open(os.path.join(os.path.dirname(__file__), 'public', 'index.html'), 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"public/index.html generated successfully with size: {len(html_content)}")
