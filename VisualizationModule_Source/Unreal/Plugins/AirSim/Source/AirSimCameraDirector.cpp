#include "AirSimCameraDirector.h"
#include "GameFramework/PlayerController.h"
#include "AirBlueprintLib.h"
#include "SimMode/SimModeBase.h"
#include <algorithm>

AAirSimCameraDirector::AAirSimCameraDirector()
{
    PrimaryActorTick.bCanEverTick = true;
    ext_obs_fixed_z_ = false;
    follow_distance_ = 12;
    camera_rotation_lag_enabled_ = true;
    mode_ = ECameraDirectorMode::CAMERA_DIRECTOR_MODE_FPV;

    // Create a spring arm component for our chase camera
    SpringArm = CreateDefaultSubobject<USpringArmComponent>(TEXT("SpringArm"));
    this->SetRootComponent(SpringArm);
    SpringArm->SetRelativeLocation(FVector(0.0f, 0.0f, 34.0f));
    SpringArm->SetWorldRotation(FRotator(-18.0f, 0.0f, 0.0f));
    SpringArm->TargetArmLength = 1200.0f;
    SpringArm->bDoCollisionTest = false;
    SpringArm->bEnableCameraLag = true;
    SpringArm->CameraLagSpeed = 6.0f;
    SpringArm->CameraLagMaxDistance = 1500.0f;
    SpringArm->bEnableCameraRotationLag = true;
    SpringArm->CameraRotationLagSpeed = 8.0f;
    SpringArm->bUsePawnControlRotation = false;
    SpringArm->bInheritPitch = false;
    SpringArm->bInheritYaw = false;
    SpringArm->bInheritRoll = false;
    SpringArm->SetUsingAbsoluteRotation(true);
}

void AAirSimCameraDirector::BeginPlay()
{
    Super::BeginPlay();
}

void AAirSimCameraDirector::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);

    syncToPossessedPawn();

    if (mode_ == ECameraDirectorMode::CAMERA_DIRECTOR_MODE_MANUAL) {
        manual_pose_controller_->updateActorPose(DeltaTime);
    }
    else if (mode_ == ECameraDirectorMode::CAMERA_DIRECTOR_MODE_SPRINGARM_CHASE) {
        updateSpringArmChase(DeltaTime);
    }
    else if (mode_ == ECameraDirectorMode::CAMERA_DIRECTOR_MODE_NODISPLAY) {
        //do nothing, we have camera turned off
    }
    else { //make camera move in desired way
        UAirBlueprintLib::FollowActor(ExternalCamera, follow_actor_, initial_ground_obs_offset_, ext_obs_fixed_z_);
    }
}

void AAirSimCameraDirector::syncToPossessedPawn()
{
    UWorld* world = GetWorld();
    if (world == nullptr) {
        return;
    }

    APlayerController* controller = world->GetFirstPlayerController();
    APawn* possessed_pawn = controller ? controller->GetPawn() : nullptr;
    if (possessed_pawn == nullptr || possessed_pawn == follow_actor_) {
        return;
    }

    follow_actor_ = possessed_pawn;

    if (const ASimModeBase* simmode = ASimModeBase::getSimMode()) {
        if (const PawnSimApi* pawn_sim_api = simmode->getVehicleSimApi(possessed_pawn)) {
            fpv_camera_ = pawn_sim_api->getCamera("fpv");
            front_camera_ = pawn_sim_api->getCamera("front_center");
            backup_camera_ = pawn_sim_api->getCamera("back_center");
        }
    }

    if (ExternalCamera != nullptr) {
        initial_ground_obs_offset_ = ExternalCamera->GetActorLocation() - follow_actor_->GetActorLocation();
    }

    if (mode_ == ECameraDirectorMode::CAMERA_DIRECTOR_MODE_SPRINGARM_CHASE) {
        resetSpringArmOrbit();
        attachSpringArm(true);
    }
}

ECameraDirectorMode AAirSimCameraDirector::getMode()
{
    return mode_;
}

void AAirSimCameraDirector::initializeForBeginPlay(ECameraDirectorMode view_mode,
                                             AActor* follow_actor, APIPCamera* fpv_camera, APIPCamera* front_camera, APIPCamera* back_camera)
{
    manual_pose_controller_ = NewObject<UManualPoseController>(this, "CameraDirector_ManualPoseController");
    manual_pose_controller_->initializeForPlay();

    setupInputBindings();

    mode_ = view_mode;

    follow_actor_ = follow_actor;
    fpv_camera_ = fpv_camera;
    front_camera_ = front_camera;
    backup_camera_ = back_camera;
    camera_start_location_ = ExternalCamera->GetActorLocation();
    camera_start_rotation_ = ExternalCamera->GetActorRotation();
    initial_ground_obs_offset_ = camera_start_location_ -
                                 (follow_actor_ ? follow_actor_->GetActorLocation() : FVector::ZeroVector);

    //set initial view mode
    switch (mode_) {
    case ECameraDirectorMode::CAMERA_DIRECTOR_MODE_FLY_WITH_ME:
        inputEventFlyWithView();
        break;
    case ECameraDirectorMode::CAMERA_DIRECTOR_MODE_FPV:
        inputEventFpvView();
        break;
    case ECameraDirectorMode::CAMERA_DIRECTOR_MODE_GROUND_OBSERVER:
        inputEventGroundView();
        break;
    case ECameraDirectorMode::CAMERA_DIRECTOR_MODE_MANUAL:
        inputEventManualView();
        break;
    case ECameraDirectorMode::CAMERA_DIRECTOR_MODE_SPRINGARM_CHASE:
        inputEventSpringArmChaseView();
        break;
    case ECameraDirectorMode::CAMERA_DIRECTOR_MODE_BACKUP:
        inputEventBackupView();
        break;
    case ECameraDirectorMode::CAMERA_DIRECTOR_MODE_NODISPLAY:
        inputEventNoDisplayView();
        break;
    case ECameraDirectorMode::CAMERA_DIRECTOR_MODE_FRONT:
        inputEventFrontView();
        break;
    default:
        throw std::out_of_range("Unsupported view mode specified in CameraDirector::initializeForBeginPlay");
    }
}

void AAirSimCameraDirector::attachSpringArm(bool attach)
{
    if (attach) {
        if (follow_actor_ == nullptr || ExternalCamera == nullptr) {
            return;
        }

        USceneComponent* follow_root = follow_actor_->GetRootComponent();
        if (follow_root == nullptr) {
            return;
        }

        // Reattach the spring arm whenever the followed pawn changes.
        if (SpringArm->GetAttachParent() != follow_root) {
            //attach spring arm to actor
            SpringArm->AttachToComponent(follow_root, FAttachmentTransformRules::KeepRelativeTransform);
            SpringArm->SetRelativeLocation(FVector(0.0f, 0.0f, 34.0f));
        }

        if (ExternalCamera->GetRootComponent()->GetAttachParent() != SpringArm) {
            //remember current parent for external camera. Later when we remove external
            //camera from spring arm, we will attach it back to its last parent
            last_parent_ = ExternalCamera->GetRootComponent()->GetAttachParent();
            ExternalCamera->DetachFromActor(FDetachmentTransformRules::KeepWorldTransform);
            //now attach camera to spring arm
            ExternalCamera->AttachToComponent(SpringArm, FAttachmentTransformRules::KeepRelativeTransform);
        }

        SpringArm->bEnableCameraLag = true;
        SpringArm->CameraLagSpeed = 6.0f;
        SpringArm->CameraLagMaxDistance = 1500.0f;
        SpringArm->bEnableCameraRotationLag = true;
        SpringArm->CameraRotationLagSpeed = camera_rotation_lag_enabled_ ? 8.0f : 12.0f;
        SpringArm->bUsePawnControlRotation = false;
        SpringArm->bInheritPitch = false;
        SpringArm->bInheritYaw = false;
        SpringArm->bInheritRoll = false;
        SpringArm->SetUsingAbsoluteRotation(true);
        SpringArm->TargetArmLength = FMath::Clamp(static_cast<float>(follow_distance_ * 100), 1200.0f, spring_arm_zoom_max_cm_);

        ExternalCamera->SetActorRelativeLocation(FVector::ZeroVector);
        ExternalCamera->SetActorRelativeRotation(FRotator::ZeroRotator);

        if (!spring_arm_orbit_initialized_) {
            resetSpringArmOrbit();
        }
        SpringArm->SetWorldRotation(FRotator(spring_arm_orbit_pitch_deg_, spring_arm_orbit_yaw_deg_, 0.0f));
    }
    else { //detach
        if (last_parent_ && ExternalCamera->GetRootComponent()->GetAttachParent() == SpringArm) {
            ExternalCamera->DetachFromActor(FDetachmentTransformRules::KeepRelativeTransform);
            ExternalCamera->AttachToComponent(last_parent_, FAttachmentTransformRules::KeepRelativeTransform);
        }
    }
}

void AAirSimCameraDirector::setMode(ECameraDirectorMode mode)
{
    { //first remove any settings done by previous mode

        //detach spring arm
        if (mode_ == ECameraDirectorMode::CAMERA_DIRECTOR_MODE_SPRINGARM_CHASE &&
            mode != ECameraDirectorMode::CAMERA_DIRECTOR_MODE_SPRINGARM_CHASE) {
            attachSpringArm(false);
        }

        // Re-enable rendering
        if (mode_ == ECameraDirectorMode::CAMERA_DIRECTOR_MODE_NODISPLAY &&
            mode != ECameraDirectorMode::CAMERA_DIRECTOR_MODE_NODISPLAY) {
            UAirBlueprintLib::enableViewportRendering(this, true);
        }

        //Remove any existing key bindings for manual mode
        if (mode != ECameraDirectorMode::CAMERA_DIRECTOR_MODE_MANUAL) {
            if (ExternalCamera != nullptr && manual_pose_controller_->getActor() == ExternalCamera) {

                manual_pose_controller_->setActor(nullptr);
            }
            //else someone else is bound to manual pose controller, leave it alone
        }
    }

    { //perform any settings to enter in to this mode

        switch (mode) {
        case ECameraDirectorMode::CAMERA_DIRECTOR_MODE_MANUAL:
            //if new mode is manual mode then add key bindings
            manual_pose_controller_->setActor(ExternalCamera);
            break;
        case ECameraDirectorMode::CAMERA_DIRECTOR_MODE_SPRINGARM_CHASE:
            //if we switched to spring arm mode then attach to spring arm (detachment was done earlier in method)
            attachSpringArm(true);
            break;
        case ECameraDirectorMode::CAMERA_DIRECTOR_MODE_NODISPLAY:
            UAirBlueprintLib::enableViewportRendering(this, false);
            break;
        default:
            //other modes don't need special setup
            break;
        }
    }

    //make switch official
    mode_ = mode;
}

void AAirSimCameraDirector::setupInputBindings()
{
    UAirBlueprintLib::EnableInput(this);

    UAirBlueprintLib::BindActionToKey("inputEventFpvView", EKeys::F, this, &AAirSimCameraDirector::inputEventFpvView);
    UAirBlueprintLib::BindActionToKey("inputEventSpringArmChaseView", EKeys::Slash, this, &AAirSimCameraDirector::inputEventSpringArmChaseView);
}

void AAirSimCameraDirector::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    manual_pose_controller_ = nullptr;
    SpringArm = nullptr;
    ExternalCamera = nullptr;
    fpv_camera_ = nullptr;
    backup_camera_ = nullptr;
    front_camera_ = nullptr;
    follow_actor_ = nullptr;
}

APIPCamera* AAirSimCameraDirector::getFpvCamera() const
{
    return fpv_camera_;
}

APIPCamera* AAirSimCameraDirector::getExternalCamera() const
{
    return ExternalCamera;
}

APIPCamera* AAirSimCameraDirector::getBackupCamera() const
{
    return backup_camera_;
}

APIPCamera* AAirSimCameraDirector::getFrontCamera() const
{
    return front_camera_;
}

void AAirSimCameraDirector::inputEventSpringArmChaseView()
{
    syncToPossessedPawn();

    if (ExternalCamera) {
        resetSpringArmOrbit();
        setMode(ECameraDirectorMode::CAMERA_DIRECTOR_MODE_SPRINGARM_CHASE);
        ExternalCamera->showToScreen();
        disableCameras(true, true, true);
    }
    else
        UAirBlueprintLib::LogMessageString("Camera is not available: ", "ExternalCamera", LogDebugLevel::Failure);

    notifyViewModeChanged();
}

void AAirSimCameraDirector::inputEventGroundView()
{
    syncToPossessedPawn();

    if (ExternalCamera) {
        setMode(ECameraDirectorMode::CAMERA_DIRECTOR_MODE_GROUND_OBSERVER);
        ExternalCamera->showToScreen();
        disableCameras(true, true, true);
        ext_obs_fixed_z_ = true;
    }
    else
        UAirBlueprintLib::LogMessageString("Camera is not available: ", "ExternalCamera", LogDebugLevel::Failure);

    notifyViewModeChanged();
}

void AAirSimCameraDirector::inputEventManualView()
{
    syncToPossessedPawn();

    if (ExternalCamera) {
        setMode(ECameraDirectorMode::CAMERA_DIRECTOR_MODE_MANUAL);
        ExternalCamera->showToScreen();
        disableCameras(true, true, true);
    }
    else
        UAirBlueprintLib::LogMessageString("Camera is not available: ", "ExternalCamera", LogDebugLevel::Failure);

    notifyViewModeChanged();
}

void AAirSimCameraDirector::inputEventNoDisplayView()
{
    syncToPossessedPawn();

    if (ExternalCamera) {
        setMode(ECameraDirectorMode::CAMERA_DIRECTOR_MODE_NODISPLAY);
        disableCameras(true, true, true);
    }
    else
        UAirBlueprintLib::LogMessageString("Camera is not available: ", "ExternalCamera", LogDebugLevel::Failure);

    notifyViewModeChanged();
}

void AAirSimCameraDirector::inputEventBackupView()
{
    syncToPossessedPawn();

    if (backup_camera_) {
        setMode(ECameraDirectorMode::CAMERA_DIRECTOR_MODE_BACKUP);
        backup_camera_->showToScreen();
        disableCameras(true, false, true);
    }
    else
        UAirBlueprintLib::LogMessageString("Camera is not available: ", "backup_camera", LogDebugLevel::Failure);

    notifyViewModeChanged();
}

void AAirSimCameraDirector::inputEventFrontView()
{
    syncToPossessedPawn();

    if (front_camera_) {
        setMode(ECameraDirectorMode::CAMERA_DIRECTOR_MODE_FRONT);
        front_camera_->showToScreen();
        disableCameras(true, true, false);
    }
    else
        UAirBlueprintLib::LogMessageString("Camera is not available: ", "backup_camera", LogDebugLevel::Failure);

    notifyViewModeChanged();
}

void AAirSimCameraDirector::inputEventFlyWithView()
{
    syncToPossessedPawn();

    if (ExternalCamera) {
        setMode(ECameraDirectorMode::CAMERA_DIRECTOR_MODE_FLY_WITH_ME);
        ExternalCamera->showToScreen();

        if (follow_actor_)
            ExternalCamera->SetActorLocationAndRotation(
                follow_actor_->GetActorLocation() + initial_ground_obs_offset_, camera_start_rotation_);
        disableCameras(true, true, true);
        ext_obs_fixed_z_ = false;
    }
    else
        UAirBlueprintLib::LogMessageString("Camera is not available: ", "ExternalCamera", LogDebugLevel::Failure);

    notifyViewModeChanged();
}

void AAirSimCameraDirector::inputEventFpvView()
{
    syncToPossessedPawn();

    if (fpv_camera_) {
        setMode(ECameraDirectorMode::CAMERA_DIRECTOR_MODE_FPV);
        fpv_camera_->showToScreen();
        disableCameras(false, true, true);
    }
    else
        UAirBlueprintLib::LogMessageString("Camera is not available: ", "fpv_camera", LogDebugLevel::Failure);

    notifyViewModeChanged();
}

void AAirSimCameraDirector::disableCameras(bool fpv, bool backup, bool front)
{
    if (fpv && fpv_camera_)
        fpv_camera_->disableMain();
    if (backup && backup_camera_)
        backup_camera_->disableMain();
    if (front && front_camera_)
        front_camera_->disableMain();
}

void AAirSimCameraDirector::notifyViewModeChanged()
{
    bool nodisplay = ECameraDirectorMode::CAMERA_DIRECTOR_MODE_NODISPLAY == mode_;

    UWorld* world = GetWorld();
    UGameViewportClient* gameViewport = world->GetGameViewport();
    gameViewport->bDisableWorldRendering = nodisplay;
}

void AAirSimCameraDirector::resetSpringArmOrbit()
{
    if (follow_actor_ == nullptr) {
        spring_arm_orbit_initialized_ = false;
        return;
    }

    spring_arm_orbit_yaw_deg_ = follow_actor_->GetActorRotation().Yaw;
    spring_arm_orbit_pitch_deg_ = -18.0f;
    spring_arm_orbit_initialized_ = true;
}

void AAirSimCameraDirector::switchVehicleByIndex(int vehicle_index)
{
    ASimModeBase* simmode = ASimModeBase::getSimMode();
    if (simmode == nullptr || simmode->getApiProvider() == nullptr) {
        return;
    }

    std::vector<std::string> vehicle_names;
    for (const auto& name : simmode->getApiProvider()->getVehicleSimApis().keys()) {
        if (!name.empty()) {
            vehicle_names.push_back(name);
        }
    }
    std::sort(vehicle_names.begin(), vehicle_names.end());

    if (vehicle_index < 0 || vehicle_index >= static_cast<int>(vehicle_names.size())) {
        return;
    }

    const std::string& vehicle_name = vehicle_names.at(vehicle_index);
    PawnSimApi* vehicle_sim_api = simmode->getVehicleSimApi(vehicle_name);
    if (vehicle_sim_api == nullptr) {
        return;
    }

    simmode->getApiProvider()->makeDefaultVehicle(vehicle_name);
    vehicle_sim_api->possess();

    follow_actor_ = vehicle_sim_api->getPawn();
    fpv_camera_ = vehicle_sim_api->getCamera("fpv");
    front_camera_ = vehicle_sim_api->getCamera("front_center");
    backup_camera_ = vehicle_sim_api->getCamera("back_center");

    resetSpringArmOrbit();
    attachSpringArm(true);
    inputEventSpringArmChaseView();
}

void AAirSimCameraDirector::updateSpringArmChase(float DeltaSeconds)
{
    (void)DeltaSeconds;

    if (follow_actor_ == nullptr || ExternalCamera == nullptr || SpringArm == nullptr) {
        return;
    }

    UWorld* world = GetWorld();
    APlayerController* controller = world ? world->GetFirstPlayerController() : nullptr;
    if (controller == nullptr) {
        return;
    }

    if (controller->WasInputKeyJustPressed(EKeys::One)) {
        switchVehicleByIndex(0);
        return;
    }
    if (controller->WasInputKeyJustPressed(EKeys::Two)) {
        switchVehicleByIndex(1);
        return;
    }
    if (controller->WasInputKeyJustPressed(EKeys::Three)) {
        switchVehicleByIndex(2);
        return;
    }
    if (controller->WasInputKeyJustPressed(EKeys::Four)) {
        switchVehicleByIndex(3);
        return;
    }
    if (controller->WasInputKeyJustPressed(EKeys::Five)) {
        switchVehicleByIndex(4);
        return;
    }

    if (controller->WasInputKeyJustPressed(EKeys::RightMouseButton)) {
        spring_arm_drag_active_ = true;
        controller->bShowMouseCursor = false;
        controller->SetInputMode(FInputModeGameOnly());
    }
    if (controller->WasInputKeyJustReleased(EKeys::RightMouseButton)) {
        spring_arm_drag_active_ = false;
        controller->bShowMouseCursor = true;
        controller->SetInputMode(FInputModeGameAndUI());
    }

    if (spring_arm_drag_active_) {
        float dx = 0.0f;
        float dy = 0.0f;
        controller->GetInputMouseDelta(dx, dy);

        spring_arm_orbit_yaw_deg_ = FMath::UnwindDegrees(spring_arm_orbit_yaw_deg_ + dx * spring_arm_orbit_yaw_speed_deg_per_px_);
        spring_arm_orbit_pitch_deg_ = FMath::Clamp(
            spring_arm_orbit_pitch_deg_ + dy * spring_arm_orbit_pitch_speed_deg_per_px_,
            spring_arm_orbit_pitch_min_deg_,
            spring_arm_orbit_pitch_max_deg_);
    }

    const float wheel_axis = controller->GetInputAnalogKeyState(EKeys::MouseWheelAxis);
    int32 wheel_step = 0;
    if (controller->WasInputKeyJustPressed(EKeys::MouseScrollUp)) {
        ++wheel_step;
    }
    if (controller->WasInputKeyJustPressed(EKeys::MouseScrollDown)) {
        --wheel_step;
    }

    float zoom_delta = 0.0f;
    if (FMath::Abs(wheel_axis) > KINDA_SMALL_NUMBER) {
        zoom_delta = -wheel_axis * spring_arm_zoom_step_cm_;
    }
    else if (wheel_step != 0) {
        zoom_delta = -static_cast<float>(wheel_step) * spring_arm_zoom_step_cm_;
    }

    if (FMath::Abs(zoom_delta) > KINDA_SMALL_NUMBER) {
        SpringArm->TargetArmLength = FMath::Clamp(
            SpringArm->TargetArmLength + zoom_delta,
            spring_arm_zoom_min_cm_,
            spring_arm_zoom_max_cm_);
    }

    SpringArm->SetWorldRotation(FRotator(spring_arm_orbit_pitch_deg_, spring_arm_orbit_yaw_deg_, 0.0f));
}
