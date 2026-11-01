Name:           linto
Version:        0.1.0
Release:        1%{?dist}
Summary:        Slicer, layout editor and streaming controller for HP-GL pen plotters

License:        GPL-3.0-or-later AND MIT
URL:            https://github.com/colorcube/linto
Source0:        %{url}/archive/v%{version}/%{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
BuildRequires:  desktop-file-utils
BuildRequires:  libappstream-glib
# %%check: the test suite runs offscreen
BuildRequires:  python3-pytest
BuildRequires:  python3-pyside6
BuildRequires:  qt6-qtbase-gui
BuildRequires:  qt6-qtsvg

Requires:       python3-pyside6
Requires:       qt6-qtsvg
Requires:       hicolor-icon-theme

%description
LINTO prepares vector graphics for HP-GL pen plotters: it places SVG and HP-GL
artwork on the sheet with the plotter's real margins, optimizes pen paths,
simulates the whole plot on screen and streams it to the plotter over RS-232
or TCP with hardware flow control.

%prep
%autosetup -n %{name}-%{version}

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files linto

install -Dpm 0644 src/linto/resources/desktop/de.colorcube.linto.desktop \
    %{buildroot}%{_datadir}/applications/de.colorcube.linto.desktop
install -Dpm 0644 src/linto/resources/desktop/de.colorcube.linto.metainfo.xml \
    %{buildroot}%{_metainfodir}/de.colorcube.linto.metainfo.xml
install -Dpm 0644 src/linto/resources/icons/linto.svg \
    %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/de.colorcube.linto.svg

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/de.colorcube.linto.desktop
appstream-util validate-relax --nonet %{buildroot}%{_metainfodir}/de.colorcube.linto.metainfo.xml
QT_QPA_PLATFORM=offscreen PYTHONPATH=%{buildroot}%{python3_sitelib} %{python3} -m pytest -q -p no:cacheprovider tests

%files -f %{pyproject_files}
%license LICENSE
%doc README.md CHANGELOG.md
%{_bindir}/linto
%{_datadir}/applications/de.colorcube.linto.desktop
%{_metainfodir}/de.colorcube.linto.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/de.colorcube.linto.svg

%changelog
* Sun Nov 01 2026 René Fritz <rf@colorcube.de> - 0.1.0-1
- First release
