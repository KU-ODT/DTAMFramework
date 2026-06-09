#include "SimHUD.h"
#include "UObject/ConstructorHelpers.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Misc/FileHelper.h"
#include "HAL/IConsoleManager.h"
#include <algorithm>

#include "Vehicles/Multirotor/SimModeWorldMultiRotor.h"
#include "Vehicles/Car/SimModeCar.h"
#include "Vehicles/SkidSteer/SimModeSkidVehicle.h"
#include "Vehicles/ComputerVision/SimModeComputerVision.h"

#include "common/AirSimSettings.hpp"
#include <stdexcept>

// DTAM: legacy CVar kept for compatibility, but DTAM now keeps 1/2/3 vehicle
// switching available because manual authority follows the current view target.
static TAutoConsoleVariable<int32> CVarDtamDisableVehicleSwitch(
    TEXT("dtam.DisableVehicleSwitch"),
    0,
    TEXT("Deprecated DTAM switch block flag. Runtime keeps 1/2/3 vehicle switching enabled."),
    ECVF_Default);

ASimHUD::ASimHUD()
{
    static ConstructorHelpers::FClassFinder<UUserWidget> hud_widget_class(TEXT("WidgetBlueprint'/AirSim/Blueprints/BP_SimHUDWidget'"));
    widget_class_ = hud_widget_class.Succeeded() ? hud_widget_class.Class : nullptr;
}

void ASimHUD::BeginPlay()
{
    Super::BeginPlay();

    try {
        UAirBlueprintLib::OnBeginPlay();
        initializeSettings();
        loadLevel();

        // Stop startup if changing levels.
        if (map_changed_) return;

        setUnrealEngineSettings();
        createSimMode();
        createMainWidget();
        setupInputBindings();
        if (simmode_)
            simmode_->startApiServer();
    }
    catch (std::exception& ex) {
        UAirBlueprintLib::LogMessageString("Error at startup: ", ex.what(), LogDebugLevel::Failure);
        //FGenericPlatformMisc::PlatformInit();
        //FGenericPlatformMisc::MessageBoxExt(EAppMsgType::Ok, TEXT("Error at Startup"), ANSI_TO_TCHAR(ex.what()));
        UAirBlueprintLib::ShowMessage(EAppMsgType::Ok, std::string("Error at startup: ") + ex.what(), "Error");
    }
}

void ASimHUD::Tick(float DeltaSeconds)
{
    if (simmode_ && simmode_->EnableReport)
        widget_->updateDebugReport(simmode_->getDebugReport());
}

void ASimHUD::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (simmode_)
        simmode_->stopApiServer();

    if (widget_) {
        widget_->Destruct();
        widget_ = nullptr;
    }
    if (simmode_) {
        simmode_->Destroy();
        simmode_ = nullptr;
    }

    UAirBlueprintLib::OnEndPlay();

    Super::EndPlay(EndPlayReason);
}

void ASimHUD::toggleRecordHandler()
{
    simmode_->toggleRecording();
}

void ASimHUD::inputEventToggleRecording()
{
    toggleRecordHandler();
}

void ASimHUD::inputEventToggleReport()
{
    simmode_->EnableReport = !simmode_->EnableReport;
    widget_->setReportVisible(simmode_->EnableReport);
}

void ASimHUD::inputEventToggleHelp()
{
    widget_->toggleHelpVisibility();
}

void ASimHUD::inputEventToggleTrace()
{
    simmode_->toggleTraceAll();
}

void ASimHUD::updateWidgetSubwindowVisibility()
{
    for (int window_index = 0; window_index < AirSimSettings::kSubwindowCount; ++window_index) {
        APIPCamera* camera = subwindow_cameras_[window_index];
        ImageType camera_type = getSubWindowSettings().at(window_index).image_type;
		std::string annotation_name = getSubWindowSettings().at(window_index).annotation_name;

        if (camera_type == ImageType::Annotation) {
            if (simmode_->DoesAnnotationLayerExist(FString(annotation_name.c_str()))) {
                bool is_visible = getSubWindowSettings().at(window_index).visible && camera != nullptr;

                if (camera != nullptr) {
                    camera->setCameraTypeEnabled(camera_type, is_visible, annotation_name);
                    //sub-window captures don't count as a request, set bCaptureEveryFrame and bCaptureOnMovement to display so we can show correctly the subwindow
                    camera->setCameraTypeUpdate(camera_type, false, annotation_name);
                }

                widget_->setSubwindowVisibility(window_index,
                    is_visible,
                    is_visible ? camera->getRenderTarget(camera_type, false, annotation_name) : nullptr);
            }
        }
        else {
            bool is_visible = getSubWindowSettings().at(window_index).visible && camera != nullptr;

            if (camera != nullptr) {
                camera->setCameraTypeEnabled(camera_type, is_visible, annotation_name);
                //sub-window captures don't count as a request, set bCaptureEveryFrame and bCaptureOnMovement to display so we can show correctly the subwindow
                camera->setCameraTypeUpdate(camera_type, false, annotation_name);
            }

            widget_->setSubwindowVisibility(window_index,
                is_visible,
                is_visible ? camera->getRenderTarget(camera_type, false, annotation_name) : nullptr);
        }
    }
}

bool ASimHUD::isWidgetSubwindowVisible(int window_index)
{
    return widget_->getSubwindowVisibility(window_index) != 0;
}

void ASimHUD::toggleSubwindowVisibility(int window_index)
{
    getSubWindowSettings().at(window_index).visible = !getSubWindowSettings().at(window_index).visible;
    updateWidgetSubwindowVisibility();
}

void ASimHUD::inputEventToggleSubwindow0()
{
    toggleSubwindowVisibility(0);
}

void ASimHUD::inputEventToggleSubwindow1()
{
    toggleSubwindowVisibility(1);
}

void ASimHUD::inputEventToggleSubwindow2()
{
    toggleSubwindowVisibility(2);
}

void ASimHUD::inputEventToggleAll()
{
    getSubWindowSettings().at(0).visible = !getSubWindowSettings().at(0).visible;
    getSubWindowSettings().at(1).visible = getSubWindowSettings().at(2).visible = getSubWindowSettings().at(0).visible;
    updateWidgetSubwindowVisibility();
}

void ASimHUD::inputEventSelectVehicle0()
{
    switchVehicleByIndex(0);
}

void ASimHUD::inputEventSelectVehicle1()
{
    switchVehicleByIndex(1);
}

void ASimHUD::inputEventSelectVehicle2()
{
    switchVehicleByIndex(2);
}

void ASimHUD::inputEventSelectVehicle3()
{
    switchVehicleByIndex(3);
}

void ASimHUD::inputEventSelectVehicle4()
{
    switchVehicleByIndex(4);
}

void ASimHUD::createMainWidget()
{
    //create main widget
    if (widget_class_ != nullptr) {
        APlayerController* player_controller = this->GetWorld()->GetFirstPlayerController();
        auto* pawn = player_controller->GetPawn();
        if (pawn) {
            std::string pawn_name = std::string(TCHAR_TO_ANSI(*pawn->GetName()));
            Utils::log(pawn_name);
        }
        else {
            UAirBlueprintLib::ShowMessage(EAppMsgType::Ok, std::string("There were no compatible vehicles created for current SimMode! Check your settings.json."), "Error");
            UAirBlueprintLib::LogMessage(TEXT("There were no compatible vehicles created for current SimMode! Check your settings.json."), TEXT(""), LogDebugLevel::Failure);
        }

        widget_ = CreateWidget<USimHUDWidget>(player_controller, widget_class_);
    }
    else {
        widget_ = nullptr;
        UAirBlueprintLib::LogMessage(TEXT("Cannot instantiate BP_SimHUDWidget blueprint!"), TEXT(""), LogDebugLevel::Failure);
    }

    initializeSubWindows();

    widget_->AddToViewport();

    //synchronize PIP views
    widget_->initializeForPlay();
    if (simmode_)
        widget_->setReportVisible(simmode_->EnableReport);
    widget_->setOnToggleRecordingHandler(std::bind(&ASimHUD::toggleRecordHandler, this));

    AirSimSettings::singleton().is_record_ui_visible = false;
    for (auto& setting : getSubWindowSettings()) {
        setting.visible = false;
    }

    widget_->setRecordButtonVisibility(false);
    updateWidgetSubwindowVisibility();
}

void ASimHUD::setUnrealEngineSettings()
{
    //TODO: should we only do below on SceneCapture2D components and cameras?
    //avoid motion blur so capture images don't get
    //GetWorld()->GetGameViewport()->GetEngineShowFlags()->SetMotionBlur(false);

    //use two different methods to set console var because sometime it doesn't seem to work
    static const auto custom_depth_var = IConsoleManager::Get().FindConsoleVariable(TEXT("r.CustomDepth"));
    custom_depth_var->Set(3);

    //Equivalent to enabling Custom Stencil in Project > Settings > Rendering > Postprocessing
    UKismetSystemLibrary::ExecuteConsoleCommand(GetWorld(), FString("r.CustomDepth 3"));

    //during startup we init stencil IDs to random hash and it takes long time for large environments
    //we get error that GameThread has timed out after 30 sec waiting on render thread
    static const auto render_timeout_var = IConsoleManager::Get().FindConsoleVariable(TEXT("g.TimeoutForBlockOnRenderFence"));
    render_timeout_var->Set(300000);
}

void ASimHUD::setupInputBindings()
{
    UAirBlueprintLib::EnableInput(this);

    UAirBlueprintLib::BindActionToKey("InputEventToggleTrace", EKeys::T, this, &ASimHUD::inputEventToggleTrace);

    UAirBlueprintLib::BindActionToKey("InputEventSelectVehicle0", EKeys::One, this, &ASimHUD::inputEventSelectVehicle0);
    UAirBlueprintLib::BindActionToKey("InputEventSelectVehicle1", EKeys::Two, this, &ASimHUD::inputEventSelectVehicle1);
    UAirBlueprintLib::BindActionToKey("InputEventSelectVehicle2", EKeys::Three, this, &ASimHUD::inputEventSelectVehicle2);
    UAirBlueprintLib::BindActionToKey("InputEventSelectVehicle3", EKeys::Four, this, &ASimHUD::inputEventSelectVehicle3);
    UAirBlueprintLib::BindActionToKey("InputEventSelectVehicle4", EKeys::Five, this, &ASimHUD::inputEventSelectVehicle4);
}

void ASimHUD::initializeSettings()
{
    std::string settingsText;
    if (getSettingsText(settingsText))
        AirSimSettings::initializeSettings(settingsText);
    else
        AirSimSettings::createDefaultSettingsFile();

    AirSimSettings::singleton().load(std::bind(&ASimHUD::getSimModeFromUser, this));
    for (const auto& warning : AirSimSettings::singleton().warning_messages) {
        UAirBlueprintLib::LogMessageString(warning, "", LogDebugLevel::Failure);
    }
    for (const auto& error : AirSimSettings::singleton().error_messages) {
        UAirBlueprintLib::ShowMessage(EAppMsgType::Ok, error, "settings.json");
    }
}

const std::vector<ASimHUD::AirSimSettings::SubwindowSetting>& ASimHUD::getSubWindowSettings() const
{
    return AirSimSettings::singleton().subwindow_settings;
}

std::vector<ASimHUD::AirSimSettings::SubwindowSetting>& ASimHUD::getSubWindowSettings()
{
    return AirSimSettings::singleton().subwindow_settings;
}

std::string ASimHUD::getSimModeFromUser()
{
    if (EAppReturnType::No == UAirBlueprintLib::ShowMessage(EAppMsgType::YesNo,
                                                            "Would you like to use car/skid-vehicle simulation? Choose no to use quadrotor simulation.",
                                                            "Choose Vehicle")) {
        return AirSimSettings::kSimModeTypeMultirotor;
    }
    else
        if (EAppReturnType::No == UAirBlueprintLib::ShowMessage(EAppMsgType::YesNo,
                                                                "Would you like to use car simulation? Choose no to use skid-vehicle simulation.",
                                                                "Choose Vehicle")) {
            return AirSimSettings::kSimModeTypeSkidVehicle;
        }
        else
            return AirSimSettings::kSimModeTypeCar;
}

void ASimHUD::loadLevel()
{
    UAirBlueprintLib::RunCommandOnGameThread([&]() { this->map_changed_ = UAirBlueprintLib::loadLevel(this->GetWorld(), FString(AirSimSettings::singleton().level_name.c_str())); }, true);
}

void ASimHUD::createSimMode()
{
    std::string simmode_name = AirSimSettings::singleton().simmode_name;

    FActorSpawnParameters simmode_spawn_params;
    simmode_spawn_params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AdjustIfPossibleButAlwaysSpawn;

    //spawn at origin. We will use this to do global NED transforms, for ex, non-vehicle objects in environment
    if (simmode_name == AirSimSettings::kSimModeTypeMultirotor)
        simmode_ = this->GetWorld()->SpawnActor<ASimModeWorldMultiRotor>(FVector::ZeroVector,
                                                                         FRotator::ZeroRotator,
                                                                         simmode_spawn_params);
    else if (simmode_name == AirSimSettings::kSimModeTypeCar)
        simmode_ = this->GetWorld()->SpawnActor<ASimModeCar>(FVector::ZeroVector,
                                                             FRotator::ZeroRotator,
                                                             simmode_spawn_params);
    else if (simmode_name == AirSimSettings::kSimModeTypeSkidVehicle)
        simmode_ = this->GetWorld()->SpawnActor<ASimModeSkidVehicle>(FVector::ZeroVector,
                                                                     FRotator::ZeroRotator,
                                                                     simmode_spawn_params);
    else if (simmode_name == AirSimSettings::kSimModeTypeComputerVision)
        simmode_ = this->GetWorld()->SpawnActor<ASimModeComputerVision>(FVector::ZeroVector,
                                                                        FRotator::ZeroRotator,
                                                                        simmode_spawn_params);
    else {
        UAirBlueprintLib::ShowMessage(EAppMsgType::Ok, std::string("SimMode is not valid: ") + simmode_name, "Error");
        UAirBlueprintLib::LogMessageString("SimMode is not valid: ", simmode_name, LogDebugLevel::Failure);
    }
}

void ASimHUD::initializeSubWindows()
{
    if (!simmode_)
        return;

    auto default_vehicle_sim_api = simmode_->getVehicleSimApi();

    if (default_vehicle_sim_api) {
        auto camera_count = default_vehicle_sim_api->getCameraCount();

        //setup defaults
        if (camera_count > 0) {
            subwindow_cameras_[0] = default_vehicle_sim_api->getCamera("");
            subwindow_cameras_[1] = default_vehicle_sim_api->getCamera(""); //camera_count > 3 ? 3 : 0
            subwindow_cameras_[2] = default_vehicle_sim_api->getCamera(""); //camera_count > 4 ? 4 : 0
        }
        else
            subwindow_cameras_[0] = subwindow_cameras_[1] = subwindow_cameras_[2] = nullptr;
    }

    for (const auto& setting : getSubWindowSettings()) {
        APIPCamera* camera = simmode_->getCamera(msr::airlib::CameraDetails(setting.camera_name, setting.vehicle_name));
        if (camera)
            subwindow_cameras_[setting.window_index] = camera;
        else
            UAirBlueprintLib::LogMessageString("Invalid Camera settings in <SubWindows> element",
                                               std::to_string(setting.window_index),
                                               LogDebugLevel::Failure);
    }
}

void ASimHUD::switchVehicleByIndex(int vehicle_index)
{
    // DTAM: Keyboard/Joystick authority follows the currently viewed vehicle,
    // so 1/2/3 vehicle switching must remain available in every control mode.
    if (simmode_ == nullptr || simmode_->getApiProvider() == nullptr) {
        return;
    }

    std::vector<std::string> vehicle_names;
    for (const auto& name : simmode_->getApiProvider()->getVehicleSimApis().keys()) {
        if (!name.empty()) {
            vehicle_names.push_back(name);
        }
    }
    std::sort(vehicle_names.begin(), vehicle_names.end());

    if (vehicle_index < 0 || vehicle_index >= static_cast<int>(vehicle_names.size())) {
        return;
    }

    const std::string& vehicle_name = vehicle_names.at(vehicle_index);
    PawnSimApi* vehicle_sim_api = simmode_->getVehicleSimApi(vehicle_name);
    if (vehicle_sim_api == nullptr) {
        return;
    }

    simmode_->getApiProvider()->makeDefaultVehicle(vehicle_name);
    vehicle_sim_api->possess();

    if (simmode_->CameraDirector != nullptr) {
        switch (simmode_->CameraDirector->getMode()) {
        case ECameraDirectorMode::CAMERA_DIRECTOR_MODE_FPV:
            simmode_->CameraDirector->inputEventFpvView();
            break;
        case ECameraDirectorMode::CAMERA_DIRECTOR_MODE_GROUND_OBSERVER:
            simmode_->CameraDirector->inputEventGroundView();
            break;
        case ECameraDirectorMode::CAMERA_DIRECTOR_MODE_FLY_WITH_ME:
            simmode_->CameraDirector->inputEventFlyWithView();
            break;
        case ECameraDirectorMode::CAMERA_DIRECTOR_MODE_MANUAL:
            simmode_->CameraDirector->inputEventManualView();
            break;
        case ECameraDirectorMode::CAMERA_DIRECTOR_MODE_SPRINGARM_CHASE:
            simmode_->CameraDirector->inputEventSpringArmChaseView();
            break;
        case ECameraDirectorMode::CAMERA_DIRECTOR_MODE_BACKUP:
            simmode_->CameraDirector->inputEventBackupView();
            break;
        case ECameraDirectorMode::CAMERA_DIRECTOR_MODE_NODISPLAY:
            simmode_->CameraDirector->inputEventNoDisplayView();
            break;
        case ECameraDirectorMode::CAMERA_DIRECTOR_MODE_FRONT:
            simmode_->CameraDirector->inputEventFrontView();
            break;
        default:
            break;
        }
    }

    UAirBlueprintLib::LogMessageString("Switched vehicle: ", vehicle_name, LogDebugLevel::Informational);
}

FString ASimHUD::getLaunchPath(const std::string& filename)
{
    FString launch_rel_path = FPaths::LaunchDir();
    FString abs_path = FPaths::ConvertRelativePathToFull(launch_rel_path);
    return FPaths::Combine(abs_path, FString(filename.c_str()));
}

// DTAMVisualization 프로젝트(.uproject) 루트 기준 경로 (주로 에디터/개발용).
FString ASimHUD::getProjectPath(const std::string& filename)
{
    FString project_rel_path = FPaths::ProjectDir();
    FString abs_path = FPaths::ConvertRelativePathToFull(project_rel_path);
    return FPaths::Combine(abs_path, FString(filename.c_str()));
}

// 실행 파일 폴더 내 ``Config/<filename>`` (배포 패키지용 사용자 편집 경로).
// 배포 시 exe 와 함께 ``Config/settings.json`` 이 배치되도록 package.bat 가 복사한다.
FString ASimHUD::getExecutableConfigPath(const std::string& filename)
{
    FString exe_folder = FString(msr::airlib::common_utils::FileSystem::getExecutableFolder().c_str());
    return FPaths::Combine(exe_folder, TEXT("Config"), FString(filename.c_str()));
}

// Attempts to parse the settings text from one of multiple locations.
//  1. command line  (-settings="<path>" 또는 -settings={...})
//  2. 배포본: <exe>/Config/settings.json       ← 사용자 편집용
//  3. 개발본: .uproject 루트/settings.json     ← 에디터에서 실행
//  4. 실행 파일 폴더/settings.json             (legacy flat)
//  5. 런치 경로/settings.json                  (legacy)
//  6. 사용자 문서 폴더 %USERPROFILE%\Documents\AirSim\settings.json (최종 fallback)
// If the settings file cannot be read, throw an exception.

bool ASimHUD::getSettingsText(std::string& settingsText)
{
    return (getSettingsTextFromCommandLine(settingsText) ||
            readSettingsTextFromFile(getExecutableConfigPath("settings.json"), settingsText) ||
            readSettingsTextFromFile(getProjectPath("settings.json"), settingsText) ||
            readSettingsTextFromFile(FString(msr::airlib::Settings::getExecutableFullPath("settings.json").c_str()), settingsText) ||
            readSettingsTextFromFile(getLaunchPath("settings.json"), settingsText) ||
            readSettingsTextFromFile(FString(msr::airlib::Settings::Settings::getUserDirectoryFullPath("settings.json").c_str()), settingsText));
}

// Attempts to parse the settings file path or the settings text from the command line
// Looks for the flag "-settings=". If it exists, settingsText will be set to the value.
// Example (Path): AirSim.exe -settings="C:\path\to\settings.json"
// Example (Text): AirSim.exe -settings={"foo":"bar"} -> settingsText will be set to {"foo":"bar"}
// Returns true if the argument is present, false otherwise.
bool ASimHUD::getSettingsTextFromCommandLine(std::string& settingsText)
{
    const TCHAR* commandLineArgs = FCommandLine::Get();
    FString settingsJsonFString;

    if (FParse::Value(commandLineArgs, TEXT("-settings="), settingsJsonFString, false)) {
        if (readSettingsTextFromFile(settingsJsonFString, settingsText)) {
            return true;
        }
        else {
            UAirBlueprintLib::LogMessageString("Loaded settings from commandline: ", TCHAR_TO_UTF8(*settingsJsonFString), LogDebugLevel::Informational);
            settingsText = TCHAR_TO_UTF8(*settingsJsonFString);
            return true;
        }
    }

    return false;
}

bool ASimHUD::readSettingsTextFromFile(const FString& settingsFilepath, std::string& settingsText)
{
    bool found = FPaths::FileExists(settingsFilepath);
    if (found) {
        FString settingsTextFStr;
        bool readSuccessful = FFileHelper::LoadFileToString(settingsTextFStr, *settingsFilepath);
        if (readSuccessful) {
            UAirBlueprintLib::LogMessageString("Loaded settings from ", TCHAR_TO_UTF8(*settingsFilepath), LogDebugLevel::Informational);
            settingsText = TCHAR_TO_UTF8(*settingsTextFStr);
        }
        else {
            UAirBlueprintLib::LogMessageString("Cannot read file ", TCHAR_TO_UTF8(*settingsFilepath), LogDebugLevel::Failure);
            throw std::runtime_error("Cannot read settings file.");
        }
    }

    return found;
}
